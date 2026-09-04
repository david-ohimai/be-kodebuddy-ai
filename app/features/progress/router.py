from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.auth import get_current_learner
from app.core.session import get_session
from app.features.auth.model import User
from app.features.activity.repository import ActivityRepository
from app.features.activity.service import ActivityService

from .repository import ProgressRepository
from .schema import CourseProgressResponse, LessonProgressResponse, ModuleProgressResponse
from .service import ProgressService


router = APIRouter(
    prefix="/progress",
    tags=["Progress"],
)


def get_progress_service(
    session: Session = Depends(get_session),
) -> ProgressService:
    progress_repository = ProgressRepository(session)

    activity_repository = ActivityRepository(session)
    activity_service = ActivityService(activity_repository)

    return ProgressService(repository=progress_repository, session=session, activity_service=activity_service,)


@router.post(
    "/lessons/{lesson_id}/toggle",
    response_model=LessonProgressResponse,
)
def toggle_lesson_completion(
    lesson_id: int,
    current_user: User = Depends(get_current_learner),
    service: ProgressService = Depends(get_progress_service),
):
    return service.toggle_lesson_completion(lesson_id, current_user)


@router.get(
    "/modules/{module_id}",
    response_model=ModuleProgressResponse,
)
def get_module_progress(
    module_id: int,
    current_user: User = Depends(get_current_learner),
    service: ProgressService = Depends(get_progress_service),
):
    return service.get_module_progress(module_id, current_user)


@router.get(
    "/courses/{course_id}",
    response_model=CourseProgressResponse,
)
def get_course_progress(
    course_id: int,
    current_user: User = Depends(get_current_learner),
    service: ProgressService = Depends(get_progress_service),
):
    return service.get_course_progress(course_id, current_user)