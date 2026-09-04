from datetime import datetime
from pydantic import BaseModel, Field
from .model import CheckInStatus


class AssignLearnerToMentor(BaseModel):
    learner_id: int


class MentorLearnerResponse(BaseModel):
    id: int
    mentor_id: int
    learner_id: int
    assigned_at: datetime

    class Config:
        from_attributes = True


class AssignedLearnerSummary(BaseModel):
    learner_id: int
    full_name: str | None
    email: str
    assigned_at: datetime



class CheckInCreate(BaseModel):
    learner_id: int
    scheduled_time: datetime
    notes: str | None = Field(default=None, max_length=1000)


class CheckInUpdate(BaseModel):
    scheduled_time: datetime | None = None
    status: CheckInStatus | None = None
    notes: str | None = Field(default=None, max_length=1000)


class CheckInResponse(BaseModel):
    id: int
    mentor_id: int
    learner_id: int
    scheduled_time: datetime
    status: CheckInStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True