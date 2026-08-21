from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssignmentCreate(BaseModel):
    module_id: int

    title: str = Field(
        min_length=2,
        max_length=255,
    )

    description: str | None = None

    due_date: datetime

    maximum_score: float = Field(
        gt=0,
    )


class AssignmentUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )

    description: str | None = None

    due_date: datetime | None = None

    maximum_score: float | None = Field(
        default=None,
        gt=0,
    )

    is_active: bool | None = None


class AssignmentResponse(BaseModel):
    id: int
    module_id: int
    title: str
    description: str | None
    due_date: datetime
    maximum_score: float
    created_by: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )