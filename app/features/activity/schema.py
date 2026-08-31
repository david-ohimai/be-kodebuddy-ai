from datetime import datetime
from pydantic import BaseModel, ConfigDict

from .model import ActivityType


class ActivityResponse(BaseModel):
    id: int
    user_id: int
    activity_type: ActivityType
    title: str
    description: str | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )