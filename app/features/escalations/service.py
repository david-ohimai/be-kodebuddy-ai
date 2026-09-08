from fastapi import HTTPException, status

from app.agent.model import Escalation
from app.features.auth.model import User
from app.features.notifications.service import NotificationService
from app.features.notifications.repository import NotificationRepository

from .repository import EscalationRepository


class EscalationService:
    def __init__(self, repository: EscalationRepository, notification_service: NotificationService | None = None):
        self.repository = repository
        self.notification_service = notification_service

    def list_for_trainer(
        self,
        trainer_id: int,
        *,
        status: str | None = None,
        course_id: int | None = None,
        learner_id: int | None = None,
    ) -> list[Escalation]:
        return self.repository.list_for_trainer(
            trainer_id,
            status=status,
            course_id=course_id,
            learner_id=learner_id,
        )

    def list_for_learner(
        self,
        learner_id: int,
        *,
        status: str | None = None,
        course_id: int | None = None,
    ) -> list[Escalation]:
        return self.repository.list_for_learner(
            learner_id,
            status=status,
            course_id=course_id,
        )

    def list_for_trainer_with_learner(
        self,
        trainer_id: int,
        *,
        status: str | None = None,
        course_id: int | None = None,
        learner_id: int | None = None,
    ) -> list[dict]:
        """Returns escalations for a trainer with learner full_name and email."""
        return self.repository.list_for_trainer_with_learner(
            trainer_id,
            status=status,
            course_id=course_id,
            learner_id=learner_id,
        )

    def list_for_learner_with_learner(
        self,
        learner_id: int,
        *,
        status: str | None = None,
        course_id: int | None = None,
    ) -> list[dict]:
        """Returns escalations for a learner with learner full_name and email."""
        return self.repository.list_for_learner_with_learner(
            learner_id,
            status=status,
            course_id=course_id,
        )

    def get_for_trainer(
        self,
        trainer_id: int,
        escalation_id: int,
    ) -> dict:
        """Returns escalation dict with learner details for a trainer."""
        escalation_data = self.repository.get_by_id_with_learner(escalation_id)
        if escalation_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escalation not found.",
            )

        if escalation_data["trainer_id"] not in (None, trainer_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to view this escalation.",
            )

        return escalation_data

    def get_for_learner(
        self,
        learner_id: int,
        escalation_id: int,
    ) -> dict:
        """Returns escalation dict with learner details for a learner."""
        escalation_data = self.repository.get_by_id_with_learner(escalation_id)
        if escalation_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escalation not found.",
            )

        if escalation_data["learner_id"] != learner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to view this escalation.",
            )

        return escalation_data

    def update_for_trainer(
        self,
        trainer_id: int,
        escalation_id: int,
        *,
        status: str | None = None,
        response: str | None = None,
    ) -> Escalation:
        # First get the escalation to check permissions
        escalation_data = self.repository.get_by_id_with_learner(escalation_id)
        if escalation_data is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escalation not found.",
            )

        if escalation_data["trainer_id"] not in (None, trainer_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to modify this escalation.",
            )

        # Get the escalation object for update
        escalation = self.repository.get_by_id(escalation_id)
        if escalation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Escalation not found.",
            )

        if escalation.trainer_id is None and trainer_id is not None:
            escalation.trainer_id = trainer_id

        updated = self.repository.update(
            escalation,
            status=status,
            response=response,
        )

        if self.notification_service is not None and updated.learner_id is not None:
            if status == "resolved":
                self.notification_service.notify_escalation_resolved(
                    learner_id=updated.learner_id,
                    trainer_id=trainer_id,
                    escalation_id=updated.id,
                )
            else:
                self.notification_service.notify_escalation_updated(
                    learner_id=updated.learner_id,
                    trainer_id=trainer_id,
                    escalation_id=updated.id,
                    status=status or updated.status,
                    response=response,
                )

        return updated