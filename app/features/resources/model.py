from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column
from sqlalchemy.types import Enum as SQLEnum
from sqlmodel import Field, SQLModel

from app.features.lessons.model import Lesson  # noqa: F401
from app.features.modules.model import Module  # noqa: F401


class ResourceType(Enum):
    FILE = "file"
    ARTICLE = "article"
    LINK = "link"


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

    lesson_id: int | None = Field(
        default=None,
        foreign_key="lessons.id",
        index=True,
    )

    title: str = Field(
        max_length=255,
    )

    description: str | None = None

    type: ResourceType = Field(
        sa_column=Column(
            SQLEnum(
                ResourceType,
                name="resourcetype",
                values_callable=lambda enum: [item.value for item in enum],
            ),
            nullable=False,
        )
    )

    url: str | None = None
    content: str | None = None

    # --- File upload fields (from Version B) ---
    file_path: str | None = Field(default=None, max_length=1024)
    file_name: str | None = Field(default=None, max_length=255)
    mime_type: str | None = Field(default=None, max_length=127)

    # --- Extraction status fields (from Version B) ---
    content_extract_status: str | None = Field(default=None, max_length=20)
    content_extract_error: str | None = None

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