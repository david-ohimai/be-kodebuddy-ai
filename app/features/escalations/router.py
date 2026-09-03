from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.auth import get_current_trainer, get_current_user
from app.core.session import get_session
from app.features.auth.model import User, UserRole

from app.features.notifications.repository import NotificationRepository
from app.features.notifications.service import NotificationService

from .repository import EscalationRepository
from .schema import EscalationResponse, EscalationUpdate
from .service import EscalationService


router = APIRouter(
    prefix="/escalations",
    tags=["Escalations"],
)


def get_escalation_service(
    session: Session = Depends(get_session),
) -> EscalationService:
    return EscalationService(
        EscalationRepository(session),
        NotificationService(NotificationRepository(session)),
    )


@router.get(
    "/trainer",
    response_model=list[EscalationResponse],
)
def list_trainer_escalations(
    status: str | None = Query(default=None),
    course_id: int | None = Query(default=None),
    learner_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_trainer),
    service: EscalationService = Depends(get_escalation_service),
):
    return service.list_for_trainer(
        current_user.id,
        status=status,
        course_id=course_id,
        learner_id=learner_id,
    )


@router.get(
    "/learner",
    response_model=list[EscalationResponse],
)
def list_learner_escalations(
    status_filter: str | None = Query(default=None, alias="status"),
    course_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    service: EscalationService = Depends(get_escalation_service),
):
    """The learner's own Escalations tab -- GET only, mirrors
    list_trainer_escalations but scoped to the caller's own rows.
    Registered ahead of GET /{escalation_id} so "/escalations/learner"
    isn't swallowed by that route's int path param."""
    if current_user.role != UserRole.LEARNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Learner access required",
        )

    return service.list_for_learner(
        current_user.id,
        status=status_filter,
        course_id=course_id,
    )

@router.get(
    "/{escalation_id}",
    response_model=EscalationResponse,
)
def get_escalation(
    escalation_id: int,
    current_user: User = Depends(get_current_user),
    service: EscalationService = Depends(get_escalation_service),
):
    """Detail view, shared by both roles: a trainer sees any escalation
    assigned to them (or unassigned), a learner sees only their own.
    No write path here for learners -- see update_escalation below,
    which stays trainer-only."""
    if current_user.role == UserRole.TRAINER:
        return service.get_for_trainer(current_user.id, escalation_id)

    if current_user.role == UserRole.LEARNER:
        return service.get_for_learner(current_user.id, escalation_id)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Trainer or learner access required",
    )


@router.patch(
    "/{escalation_id}",
    response_model=EscalationResponse,
)
def update_escalation(
    escalation_id: int,
    data: EscalationUpdate,
    current_user: User = Depends(get_current_trainer),
    service: EscalationService = Depends(get_escalation_service),
):
    if not data.status and not data.response:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a status or response update.",
        )

    return service.update_for_trainer(
        current_user.id,
        escalation_id,
        status=data.status,
        response=data.response,
    )