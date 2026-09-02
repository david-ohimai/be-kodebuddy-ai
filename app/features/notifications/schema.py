from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.features.notifications.model import NotificationType


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    notification_type: NotificationType
    related_entity_type: str | None = None
    related_entity_id: int | None = None
    is_read: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationMarkRead(BaseModel):
    is_read: bool = True
