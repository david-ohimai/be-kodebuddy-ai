from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.agent.graph.contracts import (
    EscalateToTrainerFn,
    GetAssignmentBriefFn,
    LLMClient,
    SearchAssignmentsFn,
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
    from app.agent.types import AgentRetrievalError
except ImportError:
    class AgentRetrievalError(Exception):
        pass

logger = logging.getLogger("kodebuddy.agent.graph")

MIN_RETRIEVAL_SCORE = 0.55
MIN_CONFIDENT_TOP_SCORE = 0.62
POLICY_VIOLATION_LINE_THRESHOLD = 4

_ESCALATE_CTA_WITH_DRAFT = (
    "If that doesn't cover it, you can escalate this question to your "
    "trainer and they'll follow up with you directly."
)
_ESCALATE_CTA_NO_DRAFT = (
    "You can escalate this question to your trainer and they'll follow up "
    "with you directly."
)

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
    llm: LLMClient
    search_curriculum: SearchCurriculumFn
    search_faqs: SearchFaqsFn
    get_assignment_brief: GetAssignmentBriefFn
    escalate_to_trainer: EscalateToTrainerFn
    search_assignments: SearchAssignmentsFn
    max_history_turns: int = field(default=6)


def _reset_transient_fields(state: AgentState) -> AgentState:
    return {k: v for k, v in state.items() if k in _INPUT_FIELDS}


def _validate_ids(state: AgentState) -> None:
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
                    assignment_brief = deps.get_assignment_brief(assignment_id)

            curriculum_hits = deps.search_curriculum(
                query=question, course_id=course_id, module_id=module_id
            )
            faq_hits = deps.search_faqs(query=question, course_id=course_id)
            assignment_hits = deps.search_assignments(
                query=question, course_id=course_id, module_id=module_id
            )

        except AgentRetrievalError as exc:
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

        chunks: list[RetrievedChunk] = [*curriculum_hits, *faq_hits, *assignment_hits]
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


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _parse_llm_response(raw_text: str) -> tuple[str, bool, bool]:
    stripped = raw_text.strip()

    candidates = [stripped]

    fence_match = _JSON_FENCE_PATTERN.match(stripped)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    extracted = _extract_first_json_object(stripped)
    if extracted is not None:
        candidates.append(extracted)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            answer = str(parsed["answer"]).strip()
            uncertain = bool(parsed["uncertain"])
            return answer, uncertain, False
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    salvage_match = re.search(
        r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', stripped
    )
    if salvage_match:
        try:
            salvaged_answer = json.loads(f'"{salvage_match.group(1)}"').strip()
            logger.warning(
                "reason: full JSON parse failed but salvaged 'answer' via "
                "regex; failing safe on uncertainty only"
            )
            return salvaged_answer, True, True
        except json.JSONDecodeError:
            pass

    logger.warning(
        "reason: failed to parse structured LLM output; failing safe"
    )
    return raw_text.strip(), True, True


_CODE_BLOCK_PATTERN = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)


def _violates_guide_dont_solve_policy(answer: str) -> bool:
    for block in _CODE_BLOCK_PATTERN.findall(answer):
        non_empty_lines = [line for line in block.splitlines() if line.strip()]
        if len(non_empty_lines) > POLICY_VIOLATION_LINE_THRESHOLD:
            return True
    return False


def make_reason_node(deps: AgentDependencies):

    def reason(state: AgentState) -> AgentState:
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

    def confidence_gate(state: AgentState) -> AgentState:
        chunks = state.get("retrieved_chunks", [])
        top_score = chunk_score(chunks[0]) if chunks else 0.0
        model_uncertain = bool(state.get("model_expressed_uncertainty"))
        parser_failed = bool(state.get("parser_failed"))
        policy_violation = bool(state.get("policy_violation"))

        confidence_score = 0.0 if parser_failed else top_score

        is_confident = (
            not parser_failed
            and not policy_violation
            and not model_uncertain
            and top_score >= MIN_CONFIDENT_TOP_SCORE
        )

        reason = None
        detail = None
        if not is_confident:
            if policy_violation:
                reason = EscalationReason.POLICY_VIOLATION
            elif parser_failed:
                reason = EscalationReason.PARSER_FAILURE
            elif model_uncertain:
                reason = EscalationReason.MODEL_UNCERTAINTY
            else:
                reason = EscalationReason.LOW_RETRIEVAL_CONFIDENCE
                detail = f"top retrieval score {top_score:.3f} below confidence gate"

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

    def route(state: AgentState) -> AgentState:
        if state.get("is_confident"):
            return {
                **state,
                "final_response": state["draft_response"],
                "escalated": False,
                "escalation_id": None,
                "escalation_available": False,
            }

        reason = state.get("escalation_reason") or (
            EscalationReason.LOW_RETRIEVAL_CONFIDENCE
        )

        draft = (state.get("draft_response") or "").strip()
        safe_to_show = draft and state.get("escalation_reason") != EscalationReason.POLICY_VIOLATION

        if safe_to_show:
            fallback_message = f"{draft}\n\n{_ESCALATE_CTA_WITH_DRAFT}"
        else:
            fallback_message = _ESCALATE_CTA_NO_DRAFT

        logger.info(
            "route: not confident, offering escalation — learner=%s "
            "course=%s trainer=%s reason=%s (no write performed; awaiting "
            "learner action via POST /agent/escalate)",
            state["learner_id"],
            state["course_id"],
            state.get("trainer_id"),
            reason.value,
        )

        return {
            **state,
            "final_response": fallback_message,
            "escalated": False,
            "escalation_id": None,
            "escalation_available": True,
            "escalation_reason": reason,
            "draft_response": draft if safe_to_show else "",
        }

    return route