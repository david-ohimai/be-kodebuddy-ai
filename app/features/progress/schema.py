from datetime import datetime
from pydantic import BaseModel


class LessonProgressResponse(BaseModel):
    lesson_id: int
    is_completed: bool
    completed_at: datetime | None


class ModuleProgressResponse(BaseModel):
    module_id: int
    total_lessons: int
    completed_lessons: int
    completion_percentage: float
    lessons: list[LessonProgressResponse]


class CourseProgressResponse(BaseModel):
    course_id: int
    total_modules: int
    total_lessons: int
    completed_lessons: int
    completion_percentage: float