from datetime import datetime
from pydantic import BaseModel, Field


class LessonCreate(BaseModel):
    module_id: int
    title: str = Field(min_length=1, max_length=255)
    content_body: str | None = None
    order: int = Field(default=1, ge=1)


class LessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_body: str | None = None
    order: int | None = Field(default=None, ge=1)


class LessonOrderItem(BaseModel):
    id: int
    order: int = Field(ge=1)


class ReorderLessonsRequest(BaseModel):
    module_id: int
    lessons: list[LessonOrderItem]


class LessonResponse(BaseModel):
    id: int
    module_id: int
    title: str
    content_body: str | None
    order: int
    created_by: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True