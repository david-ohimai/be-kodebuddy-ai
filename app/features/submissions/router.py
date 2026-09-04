from fastapi import APIRouter, Depends,HTTPException, status
from sqlmodel import Session

from app.core.auth import get_current_user
from app.core.session import get_session
from app.features.auth.model import User, UserRole
from app.features.activity.repository import ActivityRepository
from app.features.activity.service import ActivityService

from .repository import SubmissionRepository
from .schema import (
    GradeSubmission,
    SubmissionCreate,
    SubmissionResponse,
    SubmissionUpdate,
)
from .service import SubmissionService


router = APIRouter(
    prefix="/submissions",
    tags=["Submissions"],
)


def get_submission_service(
    session: Session = Depends(get_session)
) -> SubmissionService:
    repository = SubmissionRepository(session)
    activity_repository = ActivityRepository(session)
    activity_service = ActivityService(activity_repository)

    return SubmissionService(
        repository=repository,
        session=session,
        activity_service=activity_service,
    )


@router.post(
    "/",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    data: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service),
):

    if current_user.role != UserRole.LEARNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only learners can submit assignments.",
        )

    return service.create_submission(
        learner=current_user,
        data=data
    )


@router.get(
    "/me",
    response_model=list[SubmissionResponse],
)
def get_my_submissions(
    current_user: User = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service),
):

    if current_user.role != UserRole.LEARNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only learners can access this endpoint."
        )

    return service.get_my_submissions(
        learner=current_user
    )


@router.get(
    "/assignment/{assignment_id}",
    response_model=list[SubmissionResponse]
)
def get_assignment_submissions(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service)
):
   
    return service.get_assignment_submissions(
        assignment_id=assignment_id,
        current_user=current_user
    )


@router.get(
    "/{submission_id}",
    response_model=SubmissionResponse
)
def get_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service)
):

    return service.get_submission_by_id(
        submission_id=submission_id,
        current_user=current_user
    )


@router.patch(
    "/{submission_id}",
    response_model=SubmissionResponse
)
def update_submission(
    submission_id: int,
    data: SubmissionUpdate,
    current_user: User = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service)
):
   
    return service.update_submission(
        submission_id=submission_id,
        learner=current_user,
        data=data,
    )


@router.patch(
    "/{submission_id}/grade",
    response_model=SubmissionResponse
)
def grade_submission(
    submission_id: int,
    data: GradeSubmission,
    current_user: User = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service)
):

    return service.grade_submission(
        submission_id=submission_id,
        grader=current_user,
        data=data
    )


@router.delete(
    "/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    service: SubmissionService = Depends(get_submission_service)
):
    service.delete_submission(
        submission_id=submission_id,
        current_user=current_user
    )

    return None