"""
Service layer for the agent's request path: POST /agent/chat and
POST /agent/assignment-guidance (see router.py).

Owner: Dev D (Service & API)

This is the one place that wires together every other dev's module for a
real request:
    - Dev A's tables (via Dev B's AgentRepository, underneath the tools)
    - Dev B's tools, built per-request and scoped to the authenticated
      learner (app.agent.tools.factory.AgentTools)
    - Dev C's compiled graph (app.agent.graph.build.build_agent_graph),
      wrapped in Dev E's tracing (app.agent.tracing.build_traced_agent_graph)
      so every node/tool/LLM call for a request shows up in LangSmith when
      LANGCHAIN_TRACING_V2 is set -- a no-op passthrough otherwise, per
      tracing.py's own docstring, so this is always safe to call.
    - Dev D's own LLMClient, now a FallbackLLMClient chaining Anthropic
      (primary + a cheaper same-provider fallback), Groq, Gemini, and
      OpenRouter (see app.agent.llm) -- a single provider hiccup no longer
      fails the whole request.
    - Dev E's history read/write (app.agent.history_service)

Deliberately raises plain, FastAPI-agnostic exceptions (NotEnrolledError)
rather than fastapi.HTTPException directly, so this module has no import-time
dependency on FastAPI and can be unit tested (or reused from a script/worker)
without spinning up the app. router.py is responsible for translating these
into HTTP responses.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlmodel import Session, select

from app.agent.graph.nodes import AgentDependencies
from app.agent.graph.state import AgentState, ChatTurn, QueryType
from app.agent.graph.utils import chunk_score, get_field
from app.agent.repository import ConversationHistoryRepository, QueryLogRepository
from app.agent.tools.factory import AgentTools
from app.agent.tracing import build_traced_agent_graph
from app.agent.llm import FallbackLLMClient, GeminiLLMClient, OpenRouterLLMClient
from app.features.courses.model import CourseTrainer
from app.features.notifications.repository import NotificationRepository
from app.features.notifications.service import NotificationService
from app.core.config import AGENT_MAX_HISTORY_TURNS

logger = logging.getLogger("kodebuddy.agent.service")

# One LLM client for the process, not one per request -- these are plain
# HTTP client wrappers with no per-learner state, so there is nothing to
# gain from rebuilding them on every call, and every request pays only the
# cost of the actual API call(s).
#
# Order matters: each tier is only reached if every tier before it raises.
#   1. Anthropic, primary model (AGENT_LLM_MODEL) -- what a normal request
#      answers from.
#   2. Anthropic, fallback model (AGENT_LLM_FALLBACK_MODEL) -- same
#      provider, cheaper/faster, covers rate-limiting or overload on the
#      primary model specifically.
#   3-4. Groq, then Gemini -- genuinely different providers, so an
#      Anthropic-wide outage doesn't take the agent down with it.
#   5. OpenRouter -- broadest catch-all, since it can itself proxy to many
#      underlying models/providers.
#
# NOTE: the last tier here is OpenRouter, not Anthropic. If every tier
# fails, FallbackLLMClient re-raises OpenRouter's error, which
# app/agent/router.py's exception handling does not currently have a
# mapping for (only anthropic.* is mapped) -- a total failure will surface
# as a generic unhandled 500 instead of one of router.py's friendly
# messages. Fine for now; worth widening router.py's exception handling
# if this chain order stays for production rather than just this demo.
_llm_client = FallbackLLMClient([
    GeminiLLMClient(),
    OpenRouterLLMClient(),
])


class NotEnrolledError(Exception):
    """Raised when the authenticated learner is not enrolled in course_id.

    Checked explicitly, before building the graph, rather than letting
    retrieval silently return zero rows for an unenrolled learner: that
    would look identical to "no relevant content" and quietly escalate,
    instead of telling the caller the actual problem. See Dev B's
    AgentRepository.is_enrolled -- this is the RBAC-scoping boundary Dev B
    flagged (the "enrollment-table gap"), enforced here at the one place
    every request path goes through.
    """

    def __init__(self, learner_id: int, course_id: int) -> None:
        self.learner_id = learner_id
        self.course_id = course_id
        super().__init__(
            f"Learner {learner_id} is not enrolled in course {course_id}."
        )


@dataclass
class AgentTurnResult:
    """Service-layer result, converted to schema.AgentTurnResponse in
    router.py. A plain dataclass (not the pydantic response model itself) so
    this module stays independent of the API schema's exact shape.

    `escalated` vs `escalation_available`: `route` (nodes.py) no longer
    writes an escalation row itself, so `escalated` is always False coming
    out of a graph-driven turn today -- it's kept as a field (rather than
    dropped) because it still reflects a real write if one ever happens
    on this path in the future, and because schema.AgentTurnResponse
    exposes it as part of its stable contract. `escalation_available` is
    the field the frontend should actually branch on to decide whether to
    show an "Escalate to trainer" button; `escalation_reason` is the
    structured category, `escalation_detail` the human-readable why, and
    `draft_response` the agent's own (sanitized) best-effort answer -- all
    three meant to be forwarded as-is on POST /agent/escalate so the
    resulting row gives the trainer real context instead of a bare
    question + reason code.
    """

    answer: str
    query_type: str
    escalated: bool
    escalation_id: int | None
    escalation_available: bool
    escalation_reason: str | None
    escalation_detail: str | None
    draft_response: str | None
    confidence_score: float


def load_chat_history(
    history_repo: ConversationHistoryRepository,
    *,
    course_id: int,
    module_id: int | None,
    max_turns: int,
) -> list[ChatTurn]:
    """Loads the most recent turns as the `ChatTurn` shape AgentState
    expects (Section 7: windowed recent chat history), ready to drop
    straight into `chat_history`."""
    rows = history_repo.get_recent(
        course_id=course_id, module_id=module_id, limit=max_turns
    )
    return [ChatTurn(role=row.role.value, message=row.message) for row in rows]


def record_interaction(
    session: Session,
    *,
    learner_id: int,
    course_id: int,
    module_id: int | None,
    state: AgentState,
    latency_ms: int,
) -> None:
    """
    Persists both sides of one turn's history and the query_log row for that
    same run (Section 8: product-level logging). Called once per
    graph.invoke(), after routing.

    Deliberately takes the *final* AgentState rather than individual keyword
    args -- this is the one place that should know AgentState's shape, so
    the rest of this module doesn't need to unpack it field by field.
    latency_ms is the one exception: nothing in AgentState tracks it, since
    no node measures its own wall-clock time, so `_run_turn` below measures
    the graph.invoke() call itself and passes the result straight through.
    """
    history_repo = ConversationHistoryRepository(session, learner_id)
    history_repo.add_exchange(
        course_id=course_id,
        module_id=module_id,
        question=state["question"],
        final_response=state.get("final_response") or "",
    )

    chunks = state.get("retrieved_chunks") or []
    top_score = max((chunk_score(c) for c in chunks), default=None)
    retrieved_chunk_ids = [
        str(get_field(c, "chunk_id", default="")) for c in chunks
    ]

    query_type = state.get("query_type")
    escalation_reason = state.get("escalation_reason")

    QueryLogRepository(session).record(
        learner_id=learner_id,
        course_id=course_id,
        module_id=module_id,
        assignment_id=state.get("assignment_id"),
        query_type=(
            query_type.value if isinstance(query_type, QueryType) else query_type
        )
        or QueryType.CHAT.value,
        question=state["question"],
        retrieved_chunk_ids=retrieved_chunk_ids,
        top_retrieval_score=top_score,
        confidence_score=state.get("confidence_score", 0.0),
        is_confident=bool(state.get("is_confident", False)),
        escalated=bool(state.get("escalated", False)),
        escalation_reason=(
            escalation_reason.value
            if hasattr(escalation_reason, "value")
            else escalation_reason
        ),
        escalation_detail=state.get("escalation_detail"),
        escalation_id=state.get("escalation_id"),
        latency_ms=latency_ms,
    )

    # NOTE (previously a bugfix for the graph's own auto-escalation path):
    # `route` (app/agent/graph/nodes.py) used to write the escalation row
    # itself whenever a turn wasn't confident enough, and this block existed
    # to make sure that write also triggered notify_escalation_created --
    # otherwise a trainer would only ever find the row by manually browsing
    # the escalations dashboard.
    #
    # `route` no longer writes escalations at all (see its docstring): it
    # only sets `escalation_available`/`escalation_reason` so the frontend
    # can offer the learner a button, and the actual write + notification
    # now happen exclusively inside the learner-triggered
    # `POST /agent/escalate` endpoint (router.py::create_escalation), which
    # already calls notify_escalation_created itself.
    #
    # Practically, `state.get("escalated")` is therefore never True coming
    # out of a normal graph-driven turn today, so this block is currently
    # inert for POST /agent/chat and POST /agent/assignment-guidance. It's
    # kept (rather than deleted) purely as a safety net: if some future
    # graph path (e.g. an EXPLICIT_USER_REQUEST auto-escalation) ever does
    # set `escalated=True` directly on state again, the notification still
    # fires correctly without anyone having to remember to re-add this.
    #
    # Wrapped in try/except and logged rather than raised: were this ever to
    # fire, the escalation row would already be committed by that point, and
    # a notification-table write failure (e.g. a bad trainer_id, a
    # notifications-table outage) must not turn an already-successful
    # escalation into a 500 for the learner, nor roll back a record that a
    # trainer may still find by other means (dashboard, direct query).
    if state.get("escalated") and state.get("escalation_id") is not None:
        try:
            NotificationService(NotificationRepository(session)).notify_escalation_created(
                learner_id=learner_id,
                trainer_id=state.get("trainer_id"),
                escalation_id=state["escalation_id"],
                course_id=course_id,
                reason=(
                    escalation_reason.value
                    if hasattr(escalation_reason, "value")
                    else str(escalation_reason)
                ),
            )
        except Exception:  # noqa: BLE001 -- see comment above
            logger.exception(
                "Failed to notify trainer=%s of escalation_id=%s for "
                "learner=%s course=%s -- the escalation row itself was "
                "already committed and is not affected.",
                state.get("trainer_id"),
                state["escalation_id"],
                learner_id,
                course_id,
            )


def _resolve_trainer_id(session: Session, course_id: int) -> int | None:
    """
    Looks up the trainer assigned to a course, for AgentState.trainer_id.

    A course can have more than one CourseTrainer row (no uniqueness
    constraint on course_id alone -- see app/features/courses/model.py). This
    picks the lowest-id match deterministically. Returns None if no trainer
    is assigned, which is not an error: `route` (nodes.py) no longer writes
    escalations itself, but this value still flows into AgentState.trainer_id
    for display/telemetry purposes, and router.py's own POST /agent/escalate
    handler re-resolves trainer_id independently at write time, where None
    is likewise valid -- Dev B's escalate_to_trainer/create_escalation route
    a None trainer_id to the unassigned-escalations queue rather than
    dropping the question.
    """
    rows = session.exec(
        select(CourseTrainer)
        .where(CourseTrainer.course_id == course_id)
        .order_by(CourseTrainer.id)
    ).all()

    if not rows:
        return None
    if len(rows) > 1:
        logger.info(
            "course=%s has %d trainers assigned; using trainer_id=%s "
            "(lowest id). Revisit if courses need real load-balanced "
            "trainer assignment rather than a fixed pick.",
            course_id,
            len(rows),
            rows[0].trainer_id,
        )
    return rows[0].trainer_id


def _run_turn(
    session: Session,
    *,
    learner_id: int,
    course_id: int,
    module_id: int | None,
    assignment_id: int | None,
    question: str,
    query_type: QueryType,
) -> AgentTurnResult:
    """Shared implementation behind both public entry points below."""
    tools = AgentTools.for_learner(session, learner_id)

    if not tools.repository.is_enrolled(course_id):
        raise NotEnrolledError(learner_id, course_id)

    trainer_id = _resolve_trainer_id(session, course_id)

    # Built fresh per request, per factory.py's own guidance: the tools
    # inside `deps` are bound to this learner_id, so a graph built from them
    # must never be reused across learners or cached at module scope.
    deps = AgentDependencies(
        llm=_llm_client,
        max_history_turns=AGENT_MAX_HISTORY_TURNS,
        **tools.as_mapping(),
    )
    graph = build_traced_agent_graph(deps)

    history_repo = ConversationHistoryRepository(session, learner_id)
    chat_history = load_chat_history(
        history_repo,
        course_id=course_id,
        module_id=module_id,
        max_turns=AGENT_MAX_HISTORY_TURNS,
    )

    initial_state = {
        "learner_id": learner_id,
        "course_id": course_id,
        "module_id": module_id,
        "assignment_id": assignment_id,
        "trainer_id": trainer_id,
        "question": question,
        "query_type": query_type,
        "chat_history": chat_history,
    }

    started = time.monotonic()
    result_state = graph.invoke(initial_state)
    latency_ms = int((time.monotonic() - started) * 1000)

    record_interaction(
        session,
        learner_id=learner_id,
        course_id=course_id,
        module_id=module_id,
        state=result_state,
        latency_ms=latency_ms,
    )

    escalation_reason = result_state.get("escalation_reason")

    logger.info(
        "agent turn: learner=%s course=%s query_type=%s escalated=%s "
        "escalation_available=%s latency_ms=%d",
        learner_id,
        course_id,
        query_type.value,
        result_state.get("escalated", False),
        result_state.get("escalation_available", False),
        latency_ms,
    )

    return AgentTurnResult(
        answer=result_state.get("final_response") or "",
        query_type=query_type.value,
        escalated=bool(result_state.get("escalated", False)),
        escalation_id=result_state.get("escalation_id"),
        escalation_available=bool(result_state.get("escalation_available", False)),
        escalation_reason=(
            escalation_reason.value
            if hasattr(escalation_reason, "value")
            else escalation_reason
        ),
        escalation_detail=result_state.get("escalation_detail"),
        draft_response=result_state.get("draft_response") or "",
        confidence_score=float(result_state.get("confidence_score", 0.0)),
    )


def answer_chat_question(
    session: Session,
    *,
    learner_id: int,
    course_id: int,
    module_id: int | None,
    question: str,
) -> AgentTurnResult:
    """General curriculum/FAQ chat -- POST /agent/chat."""
    return _run_turn(
        session,
        learner_id=learner_id,
        course_id=course_id,
        module_id=module_id,
        assignment_id=None,
        question=question,
        query_type=QueryType.CHAT,
    )


def answer_assignment_guidance(
    session: Session,
    *,
    learner_id: int,
    course_id: int,
    module_id: int | None,
    assignment_id: int,
    question: str,
) -> AgentTurnResult:
    """"Guide, don't solve" assignment help -- POST /agent/assignment-guidance."""
    return _run_turn(
        session,
        learner_id=learner_id,
        course_id=course_id,
        module_id=module_id,
        assignment_id=assignment_id,
        question=question,
        query_type=QueryType.ASSIGNMENT_GUIDANCE,
    )


__all__ = [
    "AgentTurnResult",
    "NotEnrolledError",
    "load_chat_history",
    "record_interaction",
    "answer_chat_question",
    "answer_assignment_guidance",
]