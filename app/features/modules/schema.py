from datetime import datetime
from pydantic import BaseModel


class ModuleCreate(BaseModel):
    course_id: int
    title: str
    description: str | None = None
    order: int = 1


class ModuleResponse(BaseModel):
    id: int
    course_id: int
    title: str
    description: str | None
    order: int
    created_by: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True