from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel, Column


class NotificationType(str, Enum):
    ESCALATION_CREATED = "escalation_created"
    ESCALATION_UPDATED = "escalation_updated"
    ESCALATION_RESOLVED = "escalation_resolved"
    ESCALATION_ASSIGNED = "escalation_assigned"


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    title: str = Field(max_length=255, nullable=False)
    message: str = Field(nullable=False)
    notification_type: NotificationType = Field(
        sa_column=Column(
            SAEnum(
                NotificationType,
                name="notificationtype",
                values_callable=lambda enum_cls: [member.value for member in enum_cls],
            ),
            nullable=False,
            index=True,
        ),
        default=NotificationType.ESCALATION_CREATED,
    )
    related_entity_type: str | None = Field(default=None, max_length=50)
    related_entity_id: int | None = Field(default=None, index=True, nullable=True)
    is_read: bool = Field(default=False, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
