from datetime import datetime
from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    cohort_id: int

class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class AssignTrainer(BaseModel):
    trainer_id: int


class AssignLearner(BaseModel):
    learner_id: int


class CourseResponse(BaseModel):
    id: int
    title: str
    description: str | None
    cohort_id: int
    created_by: int
    is_active: bool
    created_at: datetime
    updated_at: datetime