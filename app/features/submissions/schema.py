from datetime import datetime
from pydantic import BaseModel, Field


class SubmissionCreate(BaseModel):
    assignment_id: int
    content: str = Field(min_length=1, max_length=1000)


class SubmissionUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class GradeSubmission(BaseModel):
    score: float = Field(ge=0)
    feedback: str | None = Field(default=None, max_length=1000)


class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    learner_id: int
    content: str
    submitted_at: datetime 
    score: float | None = None
    feedback: str | None = None
    graded_by: int | None = None
    graded_at: datetime | None = None
