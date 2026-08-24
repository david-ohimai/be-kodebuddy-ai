from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

from app.features.modules.model import Module  # noqa: F401 — needed so SQLAlchemy registers this table for the FK below


class Lesson(SQLModel, table=True):
    __tablename__ = "lessons"

    id: int | None = Field(default=None, primary_key=True)

    module_id: int = Field(foreign_key="modules.id", index=True)

    title: str = Field(max_length=255, index=True)
    content_body: str | None = None
    order: int = Field(default=1, index=True)

    created_by: int = Field(foreign_key="users.id", index=True)

    is_active: bool = Field(default=True, index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))