from datetime import datetime, timezone
from sqlmodel import SQLModel, Field
from sqlalchemy import UniqueConstraint

class Course(SQLModel, table=True):
    __tablename__ = "courses"

    id: int | None = Field(default=None, primary_key=True)

    title: str = Field(max_length=255)
    description: str | None = None

  # Cohort this course belongs to
    cohort_id: int = Field(
        foreign_key="cohorts.id",
        index=True,
    )

    # Admin who created the course
    created_by: int = Field(
        foreign_key="users.id",
        index=True,
    )

    is_active: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class CourseTrainer(SQLModel, table=True):
    """
    Maps trainers to the courses they are allowed to manage.
    """
    __tablename__ = "course_trainers"

    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "trainer_id",
            name="uq_course_trainer",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    course_id: int = Field(
        foreign_key="courses.id",
        index=True,
    )

    trainer_id: int = Field(
        foreign_key="users.id",
        index=True,
    )