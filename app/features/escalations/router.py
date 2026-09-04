from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.core.auth import get_current_trainer
from app.core.session import get_session
from app.features.auth.model import User

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
    "/{escalation_id}",
    response_model=EscalationResponse,
)
def get_escalation(
    escalation_id: int,
    current_user: User = Depends(get_current_trainer),
    service: EscalationService = Depends(get_escalation_service),
):
    return service.get_for_trainer(current_user.id, escalation_id)


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
