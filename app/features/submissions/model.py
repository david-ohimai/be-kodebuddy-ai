from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint

class Submission(SQLModel, table=True):
    __tablename__ = "submissions"

    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "learner_id",
            name="uq_submission_assignment_learner",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    assignment_id: int = Field(foreign_key="assignments.id", index=True)
    learner_id: int = Field(foreign_key="users.id", index=True)
    content: str = Field(min_length=1, max_length=1000)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    score: float | None = Field(default=None, ge=0)
    feedback: str | None = Field(default=None, max_length=1000)
    graded_by: int | None = Field(foreign_key="users.id", index=True)
    graded_at: datetime | None = None
    