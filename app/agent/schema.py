from datetime import datetime

from pydantic import BaseModel, Field

from app.agent.graph.state import ChatRole


# --- Dev E: conversation history (GET /agent/history) ---


class ConversationTurnResponse(BaseModel):
    id: int
    role: ChatRole
    message: str
    course_id: int
    module_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class HistoryResponse(BaseModel):
    turns: list[ConversationTurnResponse]
    total: int
    limit: int
    offset: int


# --- Dev D: unified chat entry point (POST /agent/chat) ---


class MessageRequest(BaseModel):
    """
    Single request shape for POST /agent/chat.

    `assignment_id` is optional and is the only thing that decides routing
    (see router.py::chat): present -> answer_assignment_guidance (structured
    assignment-brief lookup + "guide, don't solve" tuning); absent ->
    answer_chat_question (general curriculum/FAQ chat). Previously these
    were two separate endpoints/request shapes (ChatRequest,
    AssignmentGuidanceRequest) -- merged because the frontend chat is a
    single conversation surface that silently attaches assignment_id when
    the learner is on an assignment's page, never something the learner
    fills in themselves, so there was no real reason to force two different
    request shapes on the caller.
    """

    course_id: int
    module_id: int | None = None
    assignment_id: int | None = None
    question: str = Field(min_length=1, max_length=4000)


class AgentTurnResponse(BaseModel):
    """Response shape for /chat -- the graph produces the same output
    fields (final_response/escalated/escalation_id/confidence_score)
    regardless of query_type, so there is no reason for chat vs assignment
    guidance to disagree on response shape.

    `escalated` and `escalation_available` are deliberately distinct:

    - `escalated`: an escalation row was actually written for this turn.
      The graph itself never sets this True anymore (see
      app/agent/graph/nodes.py::make_route_node) -- it only becomes True if
      escalation is later performed out-of-band via POST /agent/escalate,
      which does not feed back into this response.
    - `escalation_available`: the agent judged this turn not confident
      enough to answer outright and is offering escalation as a choice,
      without having written anything. The frontend should use this (not
      `escalated`) to decide whether to render an "Escalate to trainer"
      button.

    When `escalation_available` is True, `escalation_reason` carries the
    structured category (an `EscalationReason` value, e.g.
    "low_retrieval_confidence") so the frontend can pass it straight
    through as the `reason` field on the POST /agent/escalate call the
    button triggers, instead of having to re-derive it from `answer` text
    or `confidence_score`.

    `escalation_detail` and `draft_response` exist for the same reason --
    to give the button enough to send a genuinely useful escalation without
    the learner typing anything extra, and to give the trainer real context
    once it lands (see EscalationCreate/EscalationResponse,
    app/features/escalations/schema.py):

    - `escalation_detail`: the graph's own human-readable note on *why* it
      wasn't confident (e.g. "Top retrieval score 0.410 did not clear the
      confidence bar."). Forward as `detail` on POST /agent/escalate.
    - `draft_response`: the agent's own best-effort answer, separate from
      `answer` (which, when not confident, is a longer wrapper message
      aimed at the learner, not something you'd want to re-send as
      structured data). Already sanitized against a policy-violating leak
      (see app/agent/graph/nodes.py::route) -- always safe to display or
      forward as `draft_response` on POST /agent/escalate. Empty string
      when the agent had nothing to show (e.g. `NO_RELEVANT_CONTEXT`,
      `RETRIEVAL_UNAVAILABLE`) or when it wasn't safe to show
      (`POLICY_VIOLATION`).
    """

    answer: str
    query_type: str
    escalated: bool
    escalation_id: int | None
    escalation_available: bool = False
    escalation_reason: str | None = None
    escalation_detail: str | None = None
    draft_response: str | None = None
    confidence_score: float