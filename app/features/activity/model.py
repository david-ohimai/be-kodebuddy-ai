from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel


class ActivityType(str, Enum):
    LESSON_COMPLETED = "lesson_completed"
    ASSIGNMENT_SUBMITTED = "assignment_submitted"
    ASSIGNMENT_GRADED = "assignment_graded"
    PROGRESS_UPDATED = "progress_updated"
    CHECK_IN_COMPLETED = "check_in_completed"


class UserActivity(SQLModel, table=True):
    __tablename__ = "user_activities"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
        nullable=False,
    )

    activity_type: ActivityType = Field(
        index=True,
        nullable=False,
    )

    title: str = Field(
        max_length=255,
        nullable=False,
    )

    description: str | None = Field(
        default=None,
        max_length=1000,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            index=True,
        ),
    )