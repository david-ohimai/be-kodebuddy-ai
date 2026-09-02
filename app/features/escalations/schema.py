from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EscalationCreate(BaseModel):
    course_id: int
    question: str = Field(min_length=1, max_length=4000)
    reason: str = Field(min_length=1, max_length=100)
    detail: str | None = None


class EscalationUpdate(BaseModel):
    status: str | None = None
    response: str | None = Field(default=None, max_length=2000)


class EscalationResponse(BaseModel):
    id: int
    learner_id: int
    course_id: int
    trainer_id: int | None = None
    question: str
    reason: str
    detail: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
