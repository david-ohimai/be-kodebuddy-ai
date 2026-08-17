from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CohortBase(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=100,
    )

    description: str | None = None

    start_date: date
    end_date: date


class CohortCreate(CohortBase):
    pass


class CohortUpdate(BaseModel):
    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class CohortResponse(CohortBase):
    id: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )



# 
# ====Assigning of cohorts to trainers


class AssignLearnerRequest(BaseModel):
    learner_id: int


class AssignTrainerRequest(BaseModel):
    trainer_id: int


class CohortLearnerResponse(BaseModel):
    id: int
    cohort_id: int
    learner_id: int
    joined_at: datetime
    completed_at: datetime | None
    is_active: bool


class CohortTrainerResponse(BaseModel):
    id: int
    cohort_id: int
    trainer_id: int
    assigned_at: datetime
    removed_at: datetime | None

from datetime import datetime
from pydantic import BaseModel


class AssignLearnerRequest(BaseModel):
    learner_id: int


class AssignTrainerRequest(BaseModel):
    trainer_id: int


class CohortLearnerResponse(BaseModel):
    id: int
    cohort_id: int
    learner_id: int
    joined_at: datetime
    completed_at: datetime | None
    is_active: bool


class CohortTrainerResponse(BaseModel):
    id: int
    cohort_id: int
    trainer_id: int
    assigned_at: datetime
    removed_at: datetime | None

class CohortDashboardResponse(BaseModel):
    cohort_id: int
    cohort_name: str

    total_learners: int
    total_trainers: int
    total_courses: int