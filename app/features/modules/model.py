from datetime import datetime
from sqlmodel import SQLModel, Field

from app.features.courses.model import Course # noqa: F401 — needed so SQLAlchemy registers this table for the FK below

class Module(SQLModel, table=True):
    __tablename__ = "modules"

    id: int | None = Field(default=None, primary_key=True)

    course_id: int = Field(foreign_key="courses.id", index=True)

    title: str
    description: str | None = None
    order: int = 1

    created_by: int = Field(foreign_key="users.id", index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)