from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, UniqueConstraint

from app.features.lessons.model import Lesson  # noqa: F401 — needed so SQLAlchemy registers this table for the FK below


class UserProgress(SQLModel, table=True):
    __tablename__ = "user_progress"

    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "lesson_id",
            name="uq_learner_lesson_progress",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    learner_id: int = Field(foreign_key="users.id", index=True)
    lesson_id: int = Field(foreign_key="lessons.id", index=True)

    is_completed: bool = Field(default=False, index=True)
    completed_at: datetime | None = None