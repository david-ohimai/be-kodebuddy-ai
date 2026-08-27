from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, UniqueConstraint
from enum import Enum


class MentorLearner(SQLModel, table=True):
    __tablename__ = "mentor_learners"

    __table_args__ = (
        UniqueConstraint(
            "mentor_id",
            "learner_id",
            name="uq_mentor_learner",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    mentor_id: int = Field(foreign_key="users.id", index=True)
    learner_id: int = Field(foreign_key="users.id", index=True)

    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CheckInStatus(str, Enum):
    UPCOMING = "upcoming"
    COMPLETED = "completed"


class MentorCheckIn(SQLModel, table=True):
    __tablename__ = "mentor_check_ins"

    id: int | None = Field(default=None, primary_key=True)

    mentor_id: int = Field(foreign_key="users.id", index=True)
    learner_id: int = Field(foreign_key="users.id", index=True)

    scheduled_time: datetime
    status: CheckInStatus = Field(default=CheckInStatus.UPCOMING)
    notes: str | None = Field(default=None, max_length=1000)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))