from datetime import datetime
from sqlmodel import SQLModel, Field

class Course(SQLModel, table=True):
    __tablename__ = "courses"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    title: str
    description: str | None = None

    created_by: int = Field(
        foreign_key="users.id",
        index=True,
    )

    is_published: bool = False

    created_at: datetime = Field(
        default_factory=datetime.utcnow
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow
    )