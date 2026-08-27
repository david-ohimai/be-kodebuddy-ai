from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field

from app.features.courses.model import Course # noqa: F401 — needed so SQLAlchemy registers this table for the FK below

class Module(SQLModel, table=True):
    __tablename__ = "modules"

    id: int | None = Field(default=None, primary_key=True)

    course_id: int = Field(foreign_key="courses.id", index=True)

    title: str = Field(max_length=255, index=True)
    description: str | None = None
    order: int = Field(default=1, index=True)

    created_by: int = Field(foreign_key="users.id", index=True)

    is_active: bool = Field(default=True, index=True)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )