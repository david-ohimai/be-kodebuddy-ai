from datetime import datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


class CohortLearner(SQLModel, table=True):
    __tablename__ = "cohort_learners"

    __table_args__ = (
        UniqueConstraint(
            "cohort_id",
            "learner_id",
            name="uq_cohort_learner",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    cohort_id: int = Field(
        foreign_key="cohorts.id",
        index=True,
    )

    learner_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    joined_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    completed_at: datetime | None = None

    is_active: bool = True


class CohortTrainer(SQLModel, table=True):
    __tablename__ = "cohort_trainers"

    __table_args__ = (
        UniqueConstraint(
            "cohort_id",
            "trainer_id",
            name="uq_cohort_trainer",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    cohort_id: int = Field(
        foreign_key="cohorts.id",
        index=True,
    )

    trainer_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    assigned_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    removed_at: datetime | None = None