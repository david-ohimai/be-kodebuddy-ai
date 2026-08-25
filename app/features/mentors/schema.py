from datetime import datetime
from pydantic import BaseModel


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