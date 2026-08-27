from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Column
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

    due_date: datetime

    maximum_score: float = Field(
        gt=0,
    )

    created_by: int = Field(
        foreign_key="users.id",
        index=True,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    is_active: bool = True