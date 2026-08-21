from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.auth import get_current_user, get_current_trainer
from app.core.session import get_session
from app.features.auth.model import User

from .repository import LessonRepository
from .schema import LessonCreate, LessonResponse, LessonUpdate, ReorderLessonsRequest
from .service import LessonService


router = APIRouter(
    prefix="/lessons",
    tags=["Lessons"],
)


def get_lesson_service(
    session: Session = Depends(get_session),
) -> LessonService:
    repository = LessonRepository(session)
    return LessonService(repository=repository, session=session)


@router.post(
    "",
    response_model=LessonResponse,
)
def create_lesson(
    data: LessonCreate,
    current_user: User = Depends(get_current_trainer),
    service: LessonService = Depends(get_lesson_service),
):
    return service.create_lesson(data, current_user)


@router.get(
    "/module/{module_id}",
    response_model=list[LessonResponse],
)
def get_module_lessons(
    module_id: int,
    current_user: User = Depends(get_current_user),
    service: LessonService = Depends(get_lesson_service),
):
    return service.get_lessons_for_module(module_id, current_user)


@router.get(
    "/{lesson_id}",
    response_model=LessonResponse,
)
def get_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_user),
    service: LessonService = Depends(get_lesson_service),
):
    return service.get_lesson(lesson_id, current_user)


@router.patch(
    "/reorder",
    response_model=list[LessonResponse],
)
def reorder_lessons(
    data: ReorderLessonsRequest,
    current_user: User = Depends(get_current_trainer),
    service: LessonService = Depends(get_lesson_service),
):
    return service.reorder_lessons(data, current_user)


@router.patch(
    "/{lesson_id}",
    response_model=LessonResponse,
)
def update_lesson(
    lesson_id: int,
    data: LessonUpdate,
    current_user: User = Depends(get_current_trainer),
    service: LessonService = Depends(get_lesson_service),
):
    return service.update_lesson(lesson_id, data, current_user)


@router.delete(
    "/{lesson_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_lesson(
    lesson_id: int,
    current_user: User = Depends(get_current_trainer),
    service: LessonService = Depends(get_lesson_service),
):
    service.delete_lesson(lesson_id, current_user)