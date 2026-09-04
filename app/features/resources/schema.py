from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ResourceCreate(BaseModel):
    title: str = Field(
        min_length=2,
        max_length=255,
    )

    description: str | None = None

    type: str = Field(
        min_length=1,
        max_length=100,
    )

    url: str | None = None


class ResourceUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=2,
        max_length=255,
    )

    description: str | None = None

    type: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    url: str | None = None

    is_active: bool | None = None


class ResourceResponse(BaseModel):
    id: int
    module_id: int
    title: str
    description: str | None
    type: str
    url: str | None
    created_by: int
    created_at: datetime
    updated_at: datetime
    is_active: bool

    model_config = ConfigDict(
        from_attributes=True
    )