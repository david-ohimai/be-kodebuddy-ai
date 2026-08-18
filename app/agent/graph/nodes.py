"""
Graph node implementations for the KodeBuddy AI agent pipeline.

Four nodes, executed in order by the compiled graph (see build.py):

    retrieve -> reason -> confidence_gate -> route

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

import logging
from dataclasses import dataclass

from app.agent.graph.contracts import (
    EscalateToTrainerFn,
    GetAssignmentBriefFn,
    LLMClient,
    SearchCurriculumFn,
    SearchFaqsFn,
)
from app.agent.graph.state import AgentState, QueryType, RetrievedChunk
from app.agent.prompts.assignment_guidance import (
    ASSIGNMENT_GUIDANCE_SYSTEM_PROMPT,
    build_assignment_user_turn,
)
from app.agent.prompts.chat import CHAT_SYSTEM_PROMPT, build_user_turn

logger = logging.getLogger("kodebuddy.agent.graph")

# --- Guardrail thresholds (tunable; Dev C owns these) ---
# A chunk below this score isn't considered "relevant" at all.
MIN_RETRIEVAL_SCORE = 0.55
# The *top* retrieved chunk must clear this higher bar for the answer to be
# considered confident — a single weak hit shouldn't be enough on its own.
MIN_CONFIDENT_TOP_SCORE = 0.62
# Windowed history size fed into the prompt (short-term continuity only).
MAX_HISTORY_TURNS_IN_PROMPT = 6


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


def make_retrieve_node(deps: AgentDependencies):
    """Returns the `retrieve` node, closed over its dependencies."""

    def retrieve(state: AgentState) -> AgentState:
        course_id = state["course_id"]
        module_id = state.get("module_id")
        question = state["question"]

        assignment_brief: str | None = None
        if state.get("query_type") == QueryType.ASSIGNMENT_GUIDANCE:
            assignment_id = state.get("assignment_id")
            if assignment_id:
                assignment_brief = _summarize_assignment_brief(
                    deps.get_assignment_brief(assignment_id)
                )

        curriculum_hits = deps.search_curriculum(
            query=question, course_id=course_id, module_id=module_id
        )
        faq_hits = deps.search_faqs(query=question, course_id=course_id)

        chunks: list[RetrievedChunk] = [*curriculum_hits, *faq_hits]
        chunks.sort(key=lambda c: c["score"], reverse=True)

        logger.info(
            "retrieve: learner=%s course=%s hits=%d top_score=%.3f",
            state["learner_id"],
            course_id,
            len(chunks),
            chunks[0]["score"] if chunks else 0.0,
        )

        return {
            **state,
            "retrieved_chunks": chunks,
            "assignment_brief": assignment_brief,
        }

    return retrieve


def _summarize_assignment_brief(brief: str | None) -> str | None:
    """Keep the core task, not the full subordinate clause.

    For example, "Build a function that reverses a string." should be reduced
    to "Build a function" so the guidance prompt stays anchored on the main
    task rather than the full assignment sentence.
    """
    if brief is None:
        return None

    cleaned = " ".join(brief.strip().split())
    lower = cleaned.lower()
    for marker in (" that ", " which ", " who ", " where ", " when ", " to "):
        idx = lower.find(marker)
        if idx != -1:
            return cleaned[:idx].strip().rstrip(".,;:")

    if "." in cleaned:
        return cleaned.split(".", 1)[0].strip()

    return cleaned


def _parse_uncertainty_flag(raw_text: str) -> tuple[str, bool]:
    """
    Splits the model's self-reported `UNCERTAIN: true/false` line (see the
    prompts) from the answer body.

    Fails safe: if the model omitted the marker or malformed it, we treat
    the response as uncertain rather than confident — an unnecessary
    escalation costs a trainer a few seconds; a false-confident wrong answer
    costs a learner's understanding.
    """
    marker = "UNCERTAIN:"
    if marker not in raw_text:
        logger.warning("reason: model omitted UNCERTAIN marker; failing safe")
        return raw_text.strip(), True

    answer_part, _, flag_part = raw_text.rpartition(marker)
    flag = flag_part.strip().lower().startswith("true")
    return answer_part.strip(), flag


def make_reason_node(deps: AgentDependencies):
    """Returns the `reason` node, closed over its dependencies."""

    def reason(state: AgentState) -> AgentState:
        chunk_texts = [c["text"] for c in state.get("retrieved_chunks", [])]
        history = state.get("chat_history", [])

        if state.get("query_type") == QueryType.ASSIGNMENT_GUIDANCE:
            system = ASSIGNMENT_GUIDANCE_SYSTEM_PROMPT
            user = build_assignment_user_turn(
                question=state["question"],
                assignment_brief=state.get("assignment_brief"),
                context_chunks=chunk_texts,
                history=history,
                max_history_turns=MAX_HISTORY_TURNS_IN_PROMPT,
            )
        else:
            system = CHAT_SYSTEM_PROMPT
            user = build_user_turn(
                question=state["question"],
                context_chunks=chunk_texts,
                history=history,
                max_history_turns=MAX_HISTORY_TURNS_IN_PROMPT,
            )

        raw = deps.llm.complete(system=system, user=user)
        answer, uncertain = _parse_uncertainty_flag(raw)

        return {
            **state,
            "draft_response": answer,
            "model_expressed_uncertainty": uncertain,
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
        top_score = chunks[0]["score"] if chunks else 0.0
        had_relevant_retrieval = top_score >= MIN_RETRIEVAL_SCORE
        model_uncertain = state.get("model_expressed_uncertainty", True)

        # Both signals must be good for a confident answer — either one
        # failing routes to escalation. Simple and explainable on purpose:
        # a trainer or Dev E reading query_logs should be able to reconstruct
        # *why* something escalated from these fields alone.
        is_confident = (
            had_relevant_retrieval
            and top_score >= MIN_CONFIDENT_TOP_SCORE
            and not model_uncertain
        )
        confidence_score = round(
            top_score * (0.0 if model_uncertain else 1.0), 4
            )

        reason = None
        if not is_confident:
            if not chunks:
                reason = "no_relevant_content_retrieved"
            elif (
                not had_relevant_retrieval
                or top_score < MIN_CONFIDENT_TOP_SCORE
            ):
                reason = "low_retrieval_relevance"
            elif model_uncertain:
                reason = "model_expressed_uncertainty"

        logger.info(
            "confidence_gate: learner=%s top_score=%.3f model_uncertain=%s "
            "is_confident=%s reason=%s",
            state["learner_id"],
            top_score,
            model_uncertain,
            is_confident,
            reason,
        )

        return {
            **state,
            "confidence_score": confidence_score,
            "is_confident": is_confident,
            "escalation_reason": reason,
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

        escalation_id = deps.escalate_to_trainer(
            learner_id=state["learner_id"],
            course_id=state["course_id"],
            question=state["question"],
            reason=state.get("escalation_reason") or "low_confidence",
        )

        draft = (state.get("draft_response") or "").strip()
        if draft:
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
            "route: escalated learner=%s course=%s escalation_id=%s reason=%s",
            state["learner_id"],
            state["course_id"],
            escalation_id,
            state.get("escalation_reason"),
        )

        return {
            **state,
            "final_response": fallback_message,
            "escalated": True,
            "escalation_id": escalation_id,
        }

    return route
