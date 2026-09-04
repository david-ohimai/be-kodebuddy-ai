from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.features.resources.model import ResourceType


class ResourceCreate(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=255,
    )

    description: str | None = None

    type: ResourceType

    url: str


class ResourceUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )

    description: str | None = None

    type: ResourceType | None = None

    url: str | None = None

    is_active: bool | None = None


class ResourceResponse(BaseModel):
    id: int
    module_id: int
    title: str
    description: str | None
    type: ResourceType
    url: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )