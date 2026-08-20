from datetime import datetime
from pydantic import BaseModel, Field


class ModuleCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    order: int = Field(default=1, ge=1)


class ModuleUpdate(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    description: str | None = None
    order: int | None = Field(
        default=None,
        ge=1,
    )

class ModuleOrderItem(BaseModel):
    id: int
    order: int = Field(ge=1)


class ReorderModulesRequest(BaseModel):
    course_id: int
    modules: list[ModuleOrderItem]


class ModuleResponse(BaseModel):
    id: int
    course_id: int
    title: str
    description: str | None
    order: int
    created_by: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True