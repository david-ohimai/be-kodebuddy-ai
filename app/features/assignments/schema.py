from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    # Optional. Omit it and the assignment is available immediately, which is
    # how assignments behaved before this field existed.
    start_date: datetime | None = None

    due_date: datetime

    maximum_score: float = Field(
        gt=0,
    )

    @model_validator(mode="after")
    def check_start_before_due(self) -> "AssignmentCreate":
        if self.start_date is not None and self.start_date >= self.due_date:
            raise ValueError("start_date must be earlier than due_date")
        return self


class AssignmentUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )

    description: str | None = None

    instructions: list[AssignmentItem] | None = None

    requirements: list[AssignmentItem] | None = None

    start_date: datetime | None = None

    due_date: datetime | None = None

    maximum_score: float | None = Field(
        default=None,
        gt=0,
    )

    is_active: bool | None = None

    @model_validator(mode="after")
    def check_start_before_due(self) -> "AssignmentUpdate":
        # Only checkable when both arrive in the same request. When just one
        # is sent, the service re-checks it against the stored value.
        if (
            self.start_date is not None
            and self.due_date is not None
            and self.start_date >= self.due_date
        ):
            raise ValueError("start_date must be earlier than due_date")
        return self


class AssignmentResponse(BaseModel):
    id: int
    module_id: int
    title: str
    description: str | None
    instructions: list[AssignmentItem] | None
    requirements: list[AssignmentItem] | None

    # NULL means the assignment is already open. The client shows the
    # "Pending / Locked" state when start_date is set and still in the future.
    start_date: datetime | None

    due_date: datetime
    maximum_score: float

    created_by: int
    # Display name of the creating trainer, resolved server-side. The client
    # cannot look this up itself: GET /users/{id} is admin-only, so a learner
    # rendering a trainer byline would get a 403 on every page load.
    # None when the user has not set a full_name.
    created_by_name: str | None = None

    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )