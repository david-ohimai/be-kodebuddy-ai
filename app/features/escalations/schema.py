from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EscalationCreate(BaseModel):
    """Body for POST /agent/escalate (app/agent/router.py::create_escalation).

    Was previously an untyped `dict` on that endpoint -- this is the actual
    request contract now, giving the frontend real validation/OpenAPI docs
    instead of a bare dict it had to get right by convention.

    `module_id`/`assignment_id`/`draft_response`/`confidence_score` are all
    optional and, when the button is driven from a chat turn, should be
    round-tripped by the frontend straight from that turn's
    MessageRequest/AgentTurnResponse rather than re-typed or re-derived --
    see AgentTurnResponse's own docstring (app/agent/schema.py) for exactly
    which response fields map to which of these.
    """

    course_id: int
    module_id: int | None = None
    assignment_id: int | None = None
    question: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=1, max_length=100)
    # Free-form "why" -- typically AgentTurnResponse.escalation_detail
    # forwarded verbatim, optionally with the learner's own note appended.
    detail: str | None = Field(default=None, max_length=2000)
    # The agent's own best-effort answer, if it had one and it was safe to
    # show (see app/agent/graph/nodes.py::route) -- typically
    # AgentTurnResponse.draft_response forwarded verbatim.
    draft_response: str | None = Field(default=None, max_length=4000)
    # The graph's confidence_score (0.0-1.0) for that draft, if any --
    # typically AgentTurnResponse.confidence_score forwarded verbatim.
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)


class EscalationUpdate(BaseModel):
    status: str | None = None
    response: str | None = Field(default=None, max_length=2000)


class EscalationResponse(BaseModel):
    id: int
    learner_id: int
    course_id: int
    module_id: int | None = None
    assignment_id: int | None = None
    trainer_id: int | None = None
    question: str
    reason: str
    detail: str | None = None
    draft_response: str | None = None
    confidence_score: float | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)