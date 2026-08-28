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
    guidance to disagree on response shape."""

    answer: str
    query_type: str
    escalated: bool
    escalation_id: int | None
    confidence_score: float