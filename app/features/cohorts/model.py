from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


class Cohort(SQLModel, table=True):
    __tablename__ = "cohorts"

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
    )

    name: str = Field(
        index=True,
        max_length=100,
    )

    description: str | None = None

    start_date: date
    end_date: date

    created_by: int = Field(
        foreign_key="users.id"
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )