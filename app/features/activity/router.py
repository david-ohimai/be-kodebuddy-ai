from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.auth import get_current_admin, get_current_learner, get_current_mentor,get_current_trainer
from app.core.session import get_session
from app.features.auth.model import User

from .model import UserActivity
from .repository import ActivityRepository
from .schema import ActivityResponse
from .service import ActivityService


router = APIRouter(
    prefix="/activity",
    tags=["Activity"],
)


def get_activity_service(
    session: Session = Depends(get_session),
) -> ActivityService:
    repository = ActivityRepository(session)

    return ActivityService(repository)

@router.get(
    "/admin",
    response_model=list[ActivityResponse],
)
def get_admin_activity(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    current_user: User = Depends(get_current_admin),
    service: ActivityService = Depends(get_activity_service),
) -> list[UserActivity]:
    return service.get_admin_activity(
        limit=limit,
    )


@router.get(
    "/trainer",
    response_model=list[ActivityResponse],
)
def get_trainer_activity(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    current_user: User = Depends(get_current_trainer),
    service: ActivityService = Depends(get_activity_service),
) -> list[UserActivity]:
    return service.get_trainer_activity(
        trainer_id=current_user.id,
        limit=limit,
    )


@router.get(
    "/mentor",
    response_model=list[ActivityResponse],
)
def get_mentor_activity(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    current_user: User = Depends(get_current_mentor),
    service: ActivityService = Depends(get_activity_service),
) -> list[UserActivity]:
    return service.get_mentor_activity(
        mentor_id=current_user.id,
        limit=limit,
    )

@router.get(
    "/learner",
    response_model=list[ActivityResponse],
)
def get_my_activity(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    current_user: User = Depends(get_current_learner),
    service: ActivityService = Depends(get_activity_service),
) -> list[UserActivity]:
    return service.get_user_activity(
        user_id=current_user.id,
        limit=limit,
    )