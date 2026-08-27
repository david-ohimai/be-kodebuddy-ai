from datetime import datetime, timezone

from sqlmodel import Field, SQLModel

class Resource(SQLModel, table=True):
    __tablename__ = "resources"

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

    type: str = Field(
        max_length=100,
    )

    url: str | None = None

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