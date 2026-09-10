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

_llm_client = FallbackLLMClient([
    OpenRouterLLMClient(),
    GeminiLLMClient(),
])

ASSIGNMENT_CONTENT_TYPE = "assignment"
MIN_RETRIEVAL_SCORE = 0.55


class NotEnrolledError(Exception):
    def __init__(self, learner_id: int, course_id: int) -> None:
        self.learner_id = learner_id
        self.course_id = course_id
        super().__init__(
            f"Learner {learner_id} is not enrolled in course {course_id}."
        )


@dataclass
class AgentTurnResult:
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
    rows = history_repo.get_recent(
        course_id=course_id, module_id=module_id, limit=max_turns
    )
    return [
        ChatTurn(
            role=row.role.value,
            message=row.message,
            retrieved_assignment_content=row.retrieved_assignment_content,
        )
        for row in rows
    ]


def _retrieved_assignment_content(chunks: list) -> bool:
    return any(
        get_field(c, "content_type", default=None) == ASSIGNMENT_CONTENT_TYPE
        and chunk_score(c) >= MIN_RETRIEVAL_SCORE
        for c in chunks
    )


def record_interaction(
    session: Session,
    *,
    learner_id: int,
    course_id: int,
    module_id: int | None,
    state: AgentState,
    latency_ms: int,
) -> None:
    history_repo = ConversationHistoryRepository(session, learner_id)
    chunks = state.get("retrieved_chunks") or []
    history_repo.add_exchange(
        course_id=course_id,
        module_id=module_id,
        question=state["question"],
        final_response=state.get("final_response") or "",
        retrieved_assignment_content=_retrieved_assignment_content(chunks),
    )

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
        except Exception:
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
    tools = AgentTools.for_learner(session, learner_id)

    if not tools.repository.is_enrolled(course_id):
        raise NotEnrolledError(learner_id, course_id)

    trainer_id = _resolve_trainer_id(session, course_id)

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

    final_response = result_state.get("final_response") or ""
    draft_response = result_state.get("draft_response") or ""

    if final_response.strip().startswith("{") and draft_response:
        logger.warning(
            "answer_chat_question/answer_assignment_guidance: final_response "
            "still looked like raw JSON for learner=%s; falling back to "
            "draft_response",
            learner_id,
        )
        final_response = draft_response

    return AgentTurnResult(
        answer=final_response,
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
        draft_response=draft_response,
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