from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column, DateTime
from sqlmodel import Field, SQLModel



class Assignment(SQLModel, table=True):
    __tablename__ = "assignments"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    module_id: int = Field(
        foreign_key="modules.id",
        index=True,
    )

    title: str = Field(
        max_length=255,
    )

    description: str | None = None


    instructions: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSON),
    )

    requirements: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column(JSON),
    )

    # When the assignment opens to learners. NULL means "available as soon as
    # it is created", which is how every assignment behaved before this column
    # existed — so existing rows keep their current behaviour.
    start_date: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    due_date: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    maximum_score: float = Field(
        gt=0,
    )

    created_by: int = Field(
        foreign_key="users.id",
        index=True,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    is_active: bool = True