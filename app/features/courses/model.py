from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import SQLModel, Field

class Course(SQLModel, table=True):
    __tablename__ = "courses"

    __table_args__ = (
        UniqueConstraint(
            "cohort_id",
            "title",
            name="uq_course_cohort_title",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    title: str = Field(max_length=255)
    description: str | None = None
    level: str | None = Field(default=None, max_length=50,)
    
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
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
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


class CourseLearner(SQLModel, table=True):
    """
    Maps learners to the courses they are assigned to.
    """
    __tablename__ = "course_learners"

    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            name="uq_course_learner_one_course",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    course_id: int = Field(
        foreign_key="courses.id",
        index=True,
    )

    learner_id: int = Field(
        foreign_key="users.id",
        index=True,
    )