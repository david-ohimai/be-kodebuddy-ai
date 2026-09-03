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
    - `route` no longer calls Dev B's `escalate_to_trainer` itself. It only
      *reasons* about whether escalation is warranted and reflects that back
      in `escalation_available`/`escalation_reason` — the actual write now
      happens exclusively via the learner-triggered `POST /agent/escalate`
      endpoint (app/agent/router.py), which the frontend calls when the
      learner taps the "Escalate to trainer" button. See `route`'s own
      docstring below for the full rationale.
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


def _extract_first_json_object(text: str) -> str | None:
    """
    Scans `text` for the first syntactically-balanced top-level `{...}`
    object and returns that substring, or None if no balanced object is
    found.

    Exists because neither Gemini nor OpenRouter is guaranteed to emit
    *only* the JSON object even when a provider-level structured-output
    constraint is requested (see app/agent/llm.py) — a model can still
    preface it with a stray "Here's my answer:" line, or a fallback tier
    that had to retry without schema enforcement can wrap it in prose. The
    old parser only handled the two cases where the whole trimmed string
    was JSON, or was JSON inside a ``` fence; both fail on a single leading
    or trailing word. This walks the string tracking brace depth and
    string/escape state (so a `{`/`}` inside a quoted "answer" value isn't
    mistaken for structural nesting) and returns the first complete
    top-level object it finds.
    """
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
    return None  # unbalanced -- no complete object found


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

    app/agent/llm.py now asks each provider to *enforce* this shape at
    generation time rather than relying solely on the prompt instruction,
    which cuts how often this function's fail-safe path fires. It stays
    here regardless, unchanged in spirit: a provider config isn't a
    guarantee, a fallback tier can still land here without schema
    enforcement, and this function must keep working against whatever text
    actually comes back.

    Tries three things, in order, before giving up:
      1. The whole trimmed response as JSON (the common case when
         provider-level structured output worked).
      2. The contents of a ```/```json fence, if the response is wrapped in
         one (a model ignoring the "no markdown fence" instruction).
      3. The first balanced top-level {...} object found anywhere in the
         response (a model that added stray prose before/after the JSON).

    Fails safe: if none of those parse into the expected shape, the raw
    text is used as the answer and both `uncertain` and `parser_failed` are
    True — an unnecessary escalation costs a trainer a few seconds; a
    false-confident wrong answer costs a learner's understanding.
    """
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
    """
    Returns the `route` node, closed over its dependencies.

    IMPORTANT — `route` no longer writes an escalation itself.

    Previously this node called `deps.escalate_to_trainer(...)` directly
    whenever `is_confident` was False, committing an `escalations` row in
    the same request that answered the learner's question — before the
    learner had any say in the matter. The product now surfaces escalation
    as a learner choice (a button in the chat UI) rather than something the
    agent silently does on their behalf, so this node's job shrinks to pure
    *reasoning*: decide whether escalation is warranted, explain that to the
    learner, and hand back enough structured info (`escalation_reason`,
    `escalation_detail`) for the frontend to render an "Escalate to trainer"
    button and, if the learner taps it, call the already-existing
    learner-triggered `POST /agent/escalate` endpoint
    (app/agent/router.py::create_escalation), which performs the actual
    write via `AgentRepository.create_escalation`.

    `deps.escalate_to_trainer` is intentionally left in `AgentDependencies`
    (unused here) rather than removed: it's still Dev B's supported way to
    write an escalation row, other callers (the manual endpoint, and any
    future auto-escalation path such as `EscalationReason.EXPLICIT_USER_REQUEST`)
    use it or an equivalent, and removing it from the dependency contract
    would be an unrelated, unnecessary break.

    `escalated`/`escalation_id` are therefore never set to a truthy value by
    this node anymore — they only ever get set once the learner actually
    escalates, via the manual endpoint's own write path, which is separate
    from graph state. This node instead sets a new field,
    `escalation_available`, so the API/frontend can distinguish "the agent
    thinks this should be escalated and is offering the option" from
    "an escalation was actually recorded".

    `draft_response` in the returned state is always safe to expose to the
    learner: on the not-confident path this node overwrites it with `""`
    whenever `safe_to_show` is False (i.e. `escalation_reason ==
    POLICY_VIOLATION`), the same guardrail that already kept an unsafe
    draft out of `final_response`. Callers (service.py, schema.py) can read
    `draft_response` straight off the final state without re-checking
    `escalation_reason` themselves.
    """

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
        # A drafted answer that itself violates "guide, don't solve" (e.g.
        # leaked a full assignment solution) must never be shown to the
        # learner just because we're now offering an escalation button
        # instead of auto-escalating — that guardrail is orthogonal to who
        # triggers the escalation write.
        safe_to_show = draft and state.get("escalation_reason") != EscalationReason.POLICY_VIOLATION

        if safe_to_show:
            fallback_message = (
                "I'm not fully confident I can give you a reliable answer to "
                "this one. Here's what I found, which may still help:\n\n"
                f"{draft}\n\n"
                "If that doesn't cover it, you can escalate this question to "
                "your trainer and they'll follow up with you directly."
            )
        else:
            fallback_message = (
                "I'm not confident I can give you a reliable answer here. "
                "You can escalate this question to your trainer and they'll "
                "follow up with you directly."
            )

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
            # Overwrite the raw draft with the already-sanitized version:
            # nothing downstream of `route` (it's the graph's terminal node)
            # needs the un-sanitized draft, and service.py/schema.py read
            # `draft_response` straight off this returned state to populate
            # AgentTurnResponse.draft_response -- if that read the raw
            # value instead, a POLICY_VIOLATION draft (a leaked assignment
            # solution) would reach the learner/frontend through that field
            # even though `safe_to_show` correctly kept it out of
            # `final_response` above. One sanitization point, not two.
            "draft_response": draft if safe_to_show else "",
        }

    return route