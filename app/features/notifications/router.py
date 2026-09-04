from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.core.auth import get_current_learner, get_current_trainer, get_current_user
from app.core.session import get_session
from app.features.auth.model import User

from .repository import NotificationRepository
from .schema import NotificationMarkRead, NotificationResponse
from .service import NotificationService


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


def get_notification_service(
    session: Session = Depends(get_session),
) -> NotificationService:
    return NotificationService(NotificationRepository(session))


@router.get(
    "",
    response_model=list[NotificationResponse],
)
def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    return service.get_user_notifications(current_user.id, limit=limit)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
def mark_notification_read(
    notification_id: int,
    data: NotificationMarkRead,
    current_user: User = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    return service.mark_as_read(
        current_user.id,
        notification_id,
        is_read=data.is_read,
    )


@router.get(
    "/trainer",
    response_model=list[NotificationResponse],
)
def list_trainer_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_trainer),
    service: NotificationService = Depends(get_notification_service),
):
    return service.get_user_notifications(current_user.id, limit=limit)


@router.get(
    "/learner",
    response_model=list[NotificationResponse],
)
def list_learner_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_learner),
    service: NotificationService = Depends(get_notification_service),
):
    return service.get_user_notifications(current_user.id, limit=limit)
