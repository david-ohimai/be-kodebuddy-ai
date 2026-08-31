"""
Graph node implementations for the KodeBuddy AI agent pipeline.

Nodes, executed by the compiled graph (see build.py):

    retrieve -> reason -> confidence_gate -> route
             -> no_context (skips reason/confidence_gate when there's
                              nothing usable to reason over) -> route

Owner: Dev C (Graph / Reasoning / Guardrails)

Dependency contract:
    - `retrieve` calls into Dev B's tools (app/agent/tools/*). Signatures are
      pinned in graph/contracts.py so this module is fully unit-testable
      against fakes before Dev B's tools land — see tests/test_graph.py.
    - `route`, on the escalation path, calls Dev B's `escalate_to_trainer`.
    - `reason` calls the LLM through an injected `LLMClient` (contracts.py),
      never a hardcoded provider SDK call, so this stays testable and
      provider-agnostic.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.agent.graph.contracts import (
    EscalateToTrainerFn,
    GetAssignmentBriefFn,
    LLMClient,
    SearchCurriculumFn,
    SearchFaqsFn,
)
from app.agent.graph.state import (
    AgentState,
    EscalationReason,
    QueryType,
    RetrievedChunk,
)
from app.agent.graph.utils import chunk_score, chunk_text
from app.agent.prompts.assignment_guidance import (
    ASSIGNMENT_GUIDANCE_SYSTEM_PROMPT,
    build_assignment_user_turn,
)
from app.agent.prompts.chat import CHAT_SYSTEM_PROMPT, build_user_turn

try:
    # Dev B's base exception for a broken retrieval pipeline (embedding
    # provider down, content-embeddings table/pgvector missing). Imported
    # from `app.agent.types` specifically, not `app.agent.tools` — the
    # former is a lightweight module with no DB dependency, so graph unit
    # tests don't need SQLModel/a database installed just to run. If this
    # import fails (e.g. an early checkout before Dev B's types module
    # exists), retrieval-failure handling simply never triggers rather than
    # breaking the whole module at import time.
    from app.agent.types import AgentRetrievalError
except ImportError:  # pragma: no cover
    class AgentRetrievalError(Exception):
        pass

logger = logging.getLogger("kodebuddy.agent.graph")

# --- Guardrail thresholds (tunable; Dev C owns these) ---
# A chunk below this score isn't considered "relevant" at all.
MIN_RETRIEVAL_SCORE = 0.55
# The *top* retrieved chunk must clear this higher bar for the answer to be
# considered confident — a single weak hit shouldn't be enough on its own.
MIN_CONFIDENT_TOP_SCORE = 0.62
# A fenced code block with more non-empty lines than this, in an assignment
# guidance response, is treated as a likely full solution rather than a
# short illustrative snippet.
POLICY_VIOLATION_LINE_THRESHOLD = 4

# Only these keys are treated as true input to a graph run. Everything else
# is stripped at the top of `retrieve` — see _reset_transient_fields.
_INPUT_FIELDS = (
    "learner_id",
    "course_id",
    "module_id",
    "assignment_id",
    "trainer_id",
    "question",
    "query_type",
    "chat_history",
)


@dataclass
class AgentDependencies:
    """
    Everything the graph needs from outside itself, injected once at
    graph-build time.

    Keeping these as injected dependencies — rather than nodes.py importing
    and calling Dev B's tools / an LLM SDK directly — is what lets this
    module be unit tested with fakes today, and lets Dev D wire in the real
    LLM client and Dev B's real tools later without touching node logic.
    """

    llm: LLMClient
    search_curriculum: SearchCurriculumFn
    search_faqs: SearchFaqsFn
    get_assignment_brief: GetAssignmentBriefFn
    escalate_to_trainer: EscalateToTrainerFn
    # Windowed history size fed into the prompt. A dataclass field (not a
    # module constant) specifically so Dev E can tune it to match how much
    # history their conversation_history query actually returns, without
    # editing nodes.py.
    max_history_turns: int = field(default=6)


def _reset_transient_fields(state: AgentState) -> AgentState:
    """
    Strips any previously-computed fields before a fresh graph run.

    Defensive against the case where a caller reuses or mutates the same
    state dict across multiple turns instead of building a fresh one per
    graph.invoke() call — without this, a prior turn's retrieved_chunks,
    is_confident, escalation_reason, etc. would leak into the current turn
    and could, for example, cause a confident answer to be returned as
    still-escalated, or vice versa.
    """
    return {k: v for k, v in state.items() if k in _INPUT_FIELDS}


def _validate_ids(state: AgentState) -> None:
    """
    Fails loudly on a type mismatch instead of letting it degrade silently.

    `learner_id`/`course_id`/`module_id`/`assignment_id`/`trainer_id` must
    be `int` to match the backend's primary keys. Without this check, a
    stray `str` id (e.g. an unconverted FastAPI path param) wouldn't raise
    anywhere — it would just make the RBAC-scoped retrieval query match
    zero rows, which looks identical to "no relevant content" and quietly
    escalates to a trainer instead of surfacing the actual bug. `bool` is
    explicitly rejected too, since `isinstance(True, int)` is `True` in
    Python and would otherwise slip through this check.
    """

    def is_valid_int(value) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    if not is_valid_int(state["learner_id"]):
        raise TypeError(f"learner_id must be int, got {state['learner_id']!r}")
    if not is_valid_int(state["course_id"]):
        raise TypeError(f"course_id must be int, got {state['course_id']!r}")

    for optional_field in ("module_id", "assignment_id", "trainer_id"):
        value = state.get(optional_field)
        if value is not None and not is_valid_int(value):
            raise TypeError(
                f"{optional_field} must be int or None, got {value!r}"
                )


def make_retrieve_node(deps: AgentDependencies):
    """Returns the `retrieve` node, closed over its dependencies."""

    def retrieve(state: AgentState) -> AgentState:
        state = _reset_transient_fields(state)
        _validate_ids(state)

        course_id = state["course_id"]
        module_id = state.get("module_id")
        question = state["question"]

        try:
            assignment_brief = None
            if state.get("query_type") == QueryType.ASSIGNMENT_GUIDANCE:
                assignment_id = state.get("assignment_id")
                if assignment_id:
                    # Full pass-through - no truncation/summarization. An
                    # assignment brief like "Build an algorithm to sort a
                    # doubly linked list" needs "doubly linked list" intact;
                    # a naive heuristic that stops at the first " to "/" that "
                    # would silently drop exactly the detail guidance
                    # depends on.
                    assignment_brief = deps.get_assignment_brief(assignment_id)

            curriculum_hits = deps.search_curriculum(
                query=question, course_id=course_id, module_id=module_id
            )
            faq_hits = deps.search_faqs(query=question, course_id=course_id)

        except AgentRetrievalError as exc:
            # The retrieval pipeline itself failed - embedding provider
            # down, content store missing - as opposed to legitimately
            # finding nothing. Dev B's tools raise rather than return `[]`
            # specifically so this is distinguishable; honour that by
            # routing to a dedicated escalation path (see build.py's
            # conditional edge) instead of either crashing the request or
            # silently treating it as "no relevant content."
            logger.error(
                "retrieve: retrieval infrastructure failure learner=%s "
                "course=%s: %s",
                state["learner_id"],
                course_id,
                exc,
            )
            return {
                **state,
                "retrieved_chunks": [],
                "assignment_brief": None,
                "retrieval_failed": True,
            }

        chunks: list[RetrievedChunk] = [*curriculum_hits, *faq_hits]
        chunks.sort(key=chunk_score, reverse=True)

        logger.info(
            "retrieve: learner=%s course=%s hits=%d top_score=%.3f",
            state["learner_id"],
            course_id,
            len(chunks),
            chunk_score(chunks[0]) if chunks else 0.0,
        )

        return {
            **state,
            "retrieved_chunks": chunks,
            "assignment_brief": assignment_brief,
            "retrieval_failed": False,
        }

    return retrieve


def make_retrieval_error_node():
    """
    Returns the `retrieval_error` node — reached directly from `retrieve`
    (see build.py's conditional edge) when retrieval raised an
    AgentRetrievalError, rather than legitimately finding nothing.

    Skips `reason`/`confidence_gate` entirely, same as `no_context`, but
    stays a separate node and a separate EscalationReason
    (RETRIEVAL_UNAVAILABLE vs NO_RELEVANT_CONTEXT) — an outage and a
    curriculum content gap look identical to a learner but need different
    follow-up from the team, and conflating them in telemetry would hide
    that.
    """

    def retrieval_error(state: AgentState) -> AgentState:
        logger.warning(
            "retrieval_error: learner=%s course=%s — retrieval infrastructure "
            "unavailable, escalating without attempting to reason",
            state["learner_id"],
            state["course_id"],
        )
        return {
            **state,
            "draft_response": "",
            "model_expressed_uncertainty": True,
            "policy_violation": False,
            "parser_failed": False,
            "confidence_score": 0.0,
            "is_confident": False,
            "escalation_reason": EscalationReason.RETRIEVAL_UNAVAILABLE,
            "escalation_detail": (
                "Curriculum/FAQ retrieval was unavailable when this "
                "question was asked."
            ),
        }

    return retrieval_error


def make_no_context_node():
    """
    Returns the `no_context` node — reached directly from `retrieve` (see
    build.py's conditional edge) when there's nothing to reason over: no
    retrieved chunks, and (for assignment guidance) no assignment brief
    either.

    Skips the LLM call entirely rather than asking the model to answer from
    nothing. This both avoids a wasted API call on every guaranteed-empty
    question, and avoids relying on the model to correctly refuse to answer
    despite having zero grounding — which it can't be guaranteed to do.
    """

    def no_context(state: AgentState) -> AgentState:
        logger.info(
            "no_context: learner=%s course=%s - skipping reasoning,"
            "no usable context",
            state["learner_id"],
            state["course_id"],
        )
        return {
            **state,
            "draft_response": "",
            "model_expressed_uncertainty": True,
            "policy_violation": False,
            "parser_failed": False,
            "confidence_score": 0.0,
            "is_confident": False,
            "escalation_reason": EscalationReason.NO_RELEVANT_CONTEXT,
            "escalation_detail": (
                "No curriculum or FAQ content, and no assignment brief, "
                "matched this question."
            ),
        }

    return no_context


_JSON_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def _parse_llm_response(raw_text: str) -> tuple[str, bool, bool]:
    """
    Parses the model's structured JSON response:
    {"answer": str, "uncertain": bool}.

    Returns (answer, uncertain, parser_failed).

    Structured JSON output replaces an earlier design that asked the model
    to end its reply with a trailing `UNCERTAIN: true/false` text marker.
    That worked with well-behaved models but smaller/fine-tuned ones
    frequently dropped the marker, which — under the old fail-safe logic —
    silently inflated the escalation rate for reasons indistinguishable
    from genuine model uncertainty. JSON mode fails more predictably, and
    failure is now its own tracked category (PARSER_FAILURE) rather than
    being folded into MODEL_UNCERTAINTY.

    Fails safe: if the response isn't valid JSON in the expected shape, the
    raw text is used as the answer and both `uncertain` and `parser_failed`
    are True — an unnecessary escalation costs a trainer a few seconds; a
    false-confident wrong answer costs a learner's understanding.
    """
    candidate = raw_text.strip()

    fence_match = _JSON_FENCE_PATTERN.match(candidate)
    if fence_match:
        candidate = fence_match.group(1).strip()

    try:
        parsed = json.loads(candidate)
        answer = str(parsed["answer"]).strip()
        uncertain = bool(parsed["uncertain"])
        return answer, uncertain, False
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.warning(
            "reason: failed to parse structured LLM output; failing safe"
            )
        return raw_text.strip(), True, True


_CODE_BLOCK_PATTERN = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)


def _violates_guide_dont_solve_policy(answer: str) -> bool:
    """
    Heuristic check for the "guide, don't solve" rule: flags a response that
    contains a fenced code block long enough to plausibly be a full working
    solution rather than a short illustrative snippet.

    Deliberately a cheap regex heuristic, not an AST-level solution
    detector — this is a guardrail net that catches the LLM ignoring the
    system prompt, not a guarantee of policy compliance. A short snippet
    under the line threshold still passes, matching the prompt's explicit
    allowance for brief illustrative examples on unrelated inputs.
    """
    for block in _CODE_BLOCK_PATTERN.findall(answer):
        non_empty_lines = [line for line in block.splitlines() if line.strip()]
        if len(non_empty_lines) > POLICY_VIOLATION_LINE_THRESHOLD:
            return True
    return False


def make_reason_node(deps: AgentDependencies):
    """Returns the `reason` node, closed over its dependencies."""

    def reason(state: AgentState) -> AgentState:
        # Filtered here, at the prompt boundary, and nowhere else: the
        # confidence gate (nodes.py::confidence_gate) and the routing
        # decision after `retrieve` (build.py::_route_after_retrieve) both
        # read state["retrieved_chunks"] directly, unfiltered. If a
        # min_score cutoff were applied at retrieval instead (in Dev B's
        # search tools), a weak-hits query would come back as an empty
        # list — indistinguishable from a genuinely empty result — and get
        # logged as NO_RELEVANT_CONTEXT instead of LOW_RETRIEVAL_CONFIDENCE,
        # collapsing a distinction Dev E's metrics rely on. Filtering only
        # `chunk_texts` keeps the gate's unfiltered top score intact while
        # still keeping sub-threshold junk out of what the model reads.
        chunk_texts = [chunk_text(c) for c in state.get(
            "retrieved_chunks", [])
            if chunk_score(c) >= MIN_RETRIEVAL_SCORE
        ]
        history = state.get("chat_history", [])
        query_type = state.get("query_type")

        if query_type == QueryType.ASSIGNMENT_GUIDANCE:
            system = ASSIGNMENT_GUIDANCE_SYSTEM_PROMPT
            user = build_assignment_user_turn(
                question=state["question"],
                assignment_brief=state.get("assignment_brief"),
                context_chunks=chunk_texts,
                history=history,
                max_history_turns=deps.max_history_turns,
            )
        else:
            system = CHAT_SYSTEM_PROMPT
            user = build_user_turn(
                question=state["question"],
                context_chunks=chunk_texts,
                history=history,
                max_history_turns=deps.max_history_turns,
            )

        raw = deps.llm.complete(system=system, user=user)
        answer, uncertain, parser_failed = _parse_llm_response(raw)

        policy_violation = False
        if query_type == QueryType.ASSIGNMENT_GUIDANCE and not parser_failed:
            policy_violation = _violates_guide_dont_solve_policy(answer)
            if policy_violation:
                logger.warning(
                    "reason: learner=%s response flagged for guide-dont-solve "
                    "policy violation",
                    state["learner_id"],
                )

        return {
            **state,
            "draft_response": answer,
            "model_expressed_uncertainty": uncertain,
            "parser_failed": parser_failed,
            "policy_violation": policy_violation,
        }

    return reason


def make_confidence_gate_node():
    """
    Returns the `confidence_gate` node. No dependencies needed — it's a pure
    function of state, which is exactly what makes it easy for Dev E to
    write regression evals against.
    """

    def confidence_gate(state: AgentState) -> AgentState:
        chunks = state.get("retrieved_chunks", [])
        top_score = chunk_score(chunks[0]) if chunks else 0.0
        had_relevant_retrieval = top_score >= MIN_RETRIEVAL_SCORE
        model_uncertain = state.get("model_expressed_uncertainty", True)
        parser_failed = state.get("parser_failed", False)
        policy_violation = state.get("policy_violation", False)

        # Every signal must be good for a confident answer — any one
        # failing routes to escalation. Simple and explainable on purpose:
        # a trainer or Dev E reading query_logs should be able to
        # reconstruct *why* something escalated from these fields alone.
        is_confident = (
            not policy_violation
            and not parser_failed
            and had_relevant_retrieval
            and top_score >= MIN_CONFIDENT_TOP_SCORE
            and not model_uncertain
        )
        confidence_score = round(
            top_score * (
                0.0 if (
                    model_uncertain or parser_failed or policy_violation
                    ) else 1.0
                ),
            4,
        )

        reason: EscalationReason | None = None
        detail: str | None = None
        if not is_confident:
            if policy_violation:
                reason = EscalationReason.POLICY_VIOLATION
                detail = (
                    "Draft response contained a code block long enough to be a full solution."
                )
            elif parser_failed:
                reason = EscalationReason.PARSER_FAILURE
                detail = "Could not parse a structured response from the model."
            elif not chunks:
                reason = EscalationReason.NO_RELEVANT_CONTEXT
                detail = "No curriculum or FAQ content was retrieved for this question."
            elif (
                    not had_relevant_retrieval
                    or top_score < MIN_CONFIDENT_TOP_SCORE
            ):
                reason = EscalationReason.LOW_RETRIEVAL_CONFIDENCE
                detail = (
                    f"Top retrieval score {top_score:.3f} did not clear the confidence bar."
                )
            elif model_uncertain:
                reason = EscalationReason.MODEL_UNCERTAINTY
                detail = "Model self-reported uncertainty about its answer."

        logger.info(
            "confidence_gate: learner=%s top_score=%.3f model_uncertain=%s "
            "parser_failed=%s policy_violation=%s is_confident=%s reason=%s",
            state["learner_id"],
            top_score,
            model_uncertain,
            parser_failed,
            policy_violation,
            is_confident,
            reason.value if reason else None,
        )

        return {
            **state,
            "confidence_score": confidence_score,
            "is_confident": is_confident,
            "escalation_reason": reason,
            "escalation_detail": detail,
        }

    return confidence_gate


def make_route_node(deps: AgentDependencies):
    """Returns the `route` node, closed over its dependencies."""

    def route(state: AgentState) -> AgentState:
        if state.get("is_confident"):
            return {
                **state,
                "final_response": state["draft_response"],
                "escalated": False,
                "escalation_id": None,
            }

        reason = state.get("escalation_reason") or (
            EscalationReason.LOW_RETRIEVAL_CONFIDENCE
        )
        trainer_id = state.get("trainer_id")

        if trainer_id is None:
            logger.warning(
                "route: escalating without a resolved trainer_id "
                "— learner=%s "
                "course=%s. Dev B's escalate_to_trainer must have a fallback "
                "(e.g. an unassigned-escalations queue) for this case.",
                state["learner_id"],
                state["course_id"],
            )

        escalation_id = deps.escalate_to_trainer(
            learner_id=state["learner_id"],
            course_id=state["course_id"],
            trainer_id=trainer_id,
            question=state["question"],
            reason=reason,
            detail=state.get("escalation_detail"),
        )

        draft = (state.get("draft_response") or "").strip()
        safe_to_show = draft and state.get("escalation_reason") != EscalationReason.POLICY_VIOLATION

        if safe_to_show:
            fallback_message = (
                "I'm not fully confident I can give you a reliable answer to "
                "this one, so I've passed it on to your trainer — they'll "
                "follow up with you directly. In the meantime, here's what I "
                f"found, which may still help:\n\n{draft}"
            )
        else:
            fallback_message = (
                "I'm not confident I can give you a reliable answer here, so "
                "I've passed this on to your trainer — they'll follow up with "
                "you directly."
            )

        logger.info(
            "route: escalated learner=%s course=%s trainer=%s "
            "escalation_id=%s reason=%s",
            state["learner_id"],
            state["course_id"],
            trainer_id,
            escalation_id,
            reason.value,
        )

        return {
            **state,
            "final_response": fallback_message,
            "escalated": True,
            "escalation_id": escalation_id,
        }

    return route
