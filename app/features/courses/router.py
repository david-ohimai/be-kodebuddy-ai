from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.auth import get_current_admin, get_current_user
from app.core.session import get_session
from app.features.auth.model import User
from app.features.cohorts.repository.repository import CohortRepository
from .repository import CourseRepository
from .schema import (
    AssignLearner,
    AssignTrainer,
    CourseCreate,
    CourseResponse,
    CourseUpdate,
)
from .service import CourseService

router = APIRouter(
    prefix="/courses",
    tags=["Courses"],
)


def get_course_service(
    session: Session = Depends(get_session),
):
    return CourseService(
        repository=CourseRepository(session),
        cohort_repository=CohortRepository(session)
    )


# ---------------- ADMIN ----------------

@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course(
    data: CourseCreate,
    current_user: User = Depends(get_current_admin),
    service: CourseService = Depends(get_course_service),
):
    return service.create_course(
        data=data,
        admin_id=current_user.id,
    )


@router.patch(
    "/{course_id}",
    response_model=CourseResponse,
)
def update_course(
    course_id: int,
    data: CourseUpdate,
    current_user: User = Depends(get_current_admin),
    service: CourseService = Depends(get_course_service),
):
    return service.update_course(course_id, data)


@router.delete(
    "/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_admin),
    service: CourseService = Depends(get_course_service),
):
    service.delete_course(course_id)


@router.post(
    "/{course_id}/assign-trainer",
)
def assign_trainer(
    course_id: int,
    data: AssignTrainer,
    current_user: User = Depends(get_current_admin),
    service: CourseService = Depends(get_course_service),
):
    return service.assign_trainer(
        course_id,
        data.trainer_id,
    )


# ---------------- ALL AUTHENTICATED USERS ----------------

@router.get(
    "",
    response_model=list[CourseResponse],
)
def get_courses(
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    return service.get_courses(current_user)


@router.get(
    "/{course_id}",
    response_model=CourseResponse,
)
def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    service: CourseService = Depends(get_course_service),
):
    return service.get_course(
        course_id,
        current_user,
    )

@router.post(
    "/{course_id}/assign-learner",
)
def assign_learner(
    course_id: int,
    data: AssignLearner,
    current_admin: User = Depends(get_current_admin),
    service: CourseService = Depends(get_course_service),
):
    return service.assign_learner(
        course_id,
        data.learner_id,
    )