from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssignmentItem(BaseModel):
    title: str
    description: str

class AssignmentCreate(BaseModel):

    title: str = Field(
        min_length=2,
        max_length=255,
    )

    description: str | None = None

    instructions: list[AssignmentItem] | None = None

    requirements: list[AssignmentItem] | None = None

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

    instructions: list[AssignmentItem] | None = None

    requirements: list[AssignmentItem] | None = None

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
    instructions: list[AssignmentItem] | None
    requirements: list[AssignmentItem] | None
    due_date: datetime
    maximum_score: float
    created_by: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )