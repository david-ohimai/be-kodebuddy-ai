"""
Prompt for the reason-specific "I'm not confident" message shown to a
learner when `route` decides to offer escalation instead of a confident
answer.

Owner: Dev C (Graph / Reasoning / Guardrails)

Kept separate from prompts/chat.py and prompts/assignment_guidance.py since
this prompt writes a short UI-facing status message, not a
question-answering completion — it doesn't take context chunks or chat
history, and its output is plain prose rather than the {"answer",
"uncertain"} JSON shape `_parse_llm_response` expects.
"""

from __future__ import annotations

from app.agent.graph.state import EscalationReason

FALLBACK_MESSAGE_SYSTEM_PROMPT = """
You write a single short message (1-2 sentences, no markdown headers) telling a 
learner that the agent isn't confident enough in an answer to their question. 
Be warm but brief -- don't over-apologize. Base the message ONLY on the reason 
given to you; never invent a cause, never mention specific scores/thresholds, 
and never reference an escalation button or trainer follow-up (that's added 
separately). Output only the message text, nothing else."""


_REASON_CONTEXT: dict[EscalationReason, str] = {
    EscalationReason.NO_RELEVANT_CONTEXT: (
        "No relevant course material could be found for this question."
    ),
    EscalationReason.LOW_RETRIEVAL_CONFIDENCE: (
        "The course material found only weakly matches this question."
    ),
    EscalationReason.MODEL_UNCERTAINTY: (
        "The model itself flagged its own answer as uncertain."
    ),
    EscalationReason.POLICY_VIOLATION: (
        "The draft would have handed over a full assignment solution, so "
        "it can't be shown."
    ),
    EscalationReason.PARSER_FAILURE: (
        "The model's response came back in an unexpected format."
    ),
    EscalationReason.RETRIEVAL_UNAVAILABLE: (
        "The course-material search was unavailable when answering."
    ),
    EscalationReason.EXPLICIT_USER_REQUEST: (
        "The learner asked to speak with their trainer directly."
    ),
}


def build_fallback_user_turn(
    *,
    reason: EscalationReason,
    detail: str | None,
    question: str,
    has_draft: bool,
) -> str:
    """
    Builds the user turn for FALLBACK_MESSAGE_SYSTEM_PROMPT.

    `has_draft` tells the model whether a draft answer will be shown right
    after its message (so it can, e.g., say "here's what I found" style
    framing) without actually handing the model the draft content itself --
    the draft is appended by `route` verbatim, never paraphrased by the LLM.
    """
    lines = [
        f"Learner's question: {question}",
        f"Why we're not confident: {_REASON_CONTEXT[reason]}",
    ]
    if detail:
        lines.append(f"Additional detail: {detail}")
    lines.append(
        "A partial draft answer will be shown right after your message."
        if has_draft
        else "No draft answer exists to show."
    )
    return "\n".join(lines)