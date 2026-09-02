from fastapi import HTTPException, status

from app.features.notifications.model import Notification, NotificationType
from app.features.notifications.repository import NotificationRepository


class NotificationService:
    def __init__(self, repository: NotificationRepository):
        self.repository = repository

    def create_for_user(
        self,
        *,
        user_id: int,
        title: str,
        message: str,
        notification_type: str,
        related_entity_type: str | None = None,
        related_entity_id: int | None = None,
    ) -> Notification:
        return self.repository.create(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )

    def get_user_notifications(self, user_id: int, *, limit: int = 50) -> list[Notification]:
        return self.repository.list_for_user(user_id, limit=limit)

    def mark_as_read(self, user_id: int, notification_id: int, *, is_read: bool = True) -> Notification:
        notification = self.repository.mark_read(notification_id, user_id, is_read=is_read)
        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found.",
            )
        return notification

    def notify_escalation_created(
        self,
        *,
        learner_id: int,
        trainer_id: int | None,
        escalation_id: int,
        course_id: int,
        reason: str,
    ) -> list[Notification]:
        notifications: list[Notification] = []

        if trainer_id is not None:
            notifications.append(
                self.create_for_user(
                    user_id=trainer_id,
                    title="New escalation received",
                    message=(
                        f"A learner has escalated a question in course {course_id}. "
                        f"Reason: {reason}."
                    ),
                    notification_type=NotificationType.ESCALATION_CREATED.value,
                    related_entity_type="escalation",
                    related_entity_id=escalation_id,
                )
            )

        notifications.append(
            self.create_for_user(
                user_id=learner_id,
                title="Escalation submitted",
                message=(
                    "Your case has been escalated to the trainer and is now pending review."
                ),
                notification_type=NotificationType.ESCALATION_CREATED.value,
                related_entity_type="escalation",
                related_entity_id=escalation_id,
            )
        )

        return notifications

    def notify_escalation_updated(
        self,
        *,
        learner_id: int,
        trainer_id: int,
        escalation_id: int,
        status: str,
        response: str | None = None,
    ) -> list[Notification]:
        notifications: list[Notification] = []

        trainer_msg = response.strip() if response else "The escalation has been updated."
        notifications.append(
            self.create_for_user(
                user_id=learner_id,
                title="Escalation status updated",
                message=(
                    f"Your escalation has been attended to by trainer {trainer_id}. "
                    f"Status: {status}. {trainer_msg}"
                ),
                notification_type=NotificationType.ESCALATION_UPDATED.value,
                related_entity_type="escalation",
                related_entity_id=escalation_id,
            )
        )

        notifications.append(
            self.create_for_user(
                user_id=trainer_id,
                title="Escalation updated",
                message=(
                    f"You updated escalation #{escalation_id}. "
                    f"Status: {status}."
                ),
                notification_type=NotificationType.ESCALATION_UPDATED.value,
                related_entity_type="escalation",
                related_entity_id=escalation_id,
            )
        )

        return notifications

    def notify_escalation_resolved(
        self,
        *,
        learner_id: int,
        trainer_id: int,
        escalation_id: int,
    ) -> list[Notification]:
        notifications: list[Notification] = []

        notifications.append(
            self.create_for_user(
                user_id=learner_id,
                title="Escalation resolved",
                message=(
                    f"Your escalation has been attended to by trainer {trainer_id}. "
                    "You can continue with the course guidance now."
                ),
                notification_type=NotificationType.ESCALATION_RESOLVED.value,
                related_entity_type="escalation",
                related_entity_id=escalation_id,
            )
        )

        notifications.append(
            self.create_for_user(
                user_id=trainer_id,
                title="Escalation resolved",
                message=(
                    f"You marked escalation #{escalation_id} as resolved."
                ),
                notification_type=NotificationType.ESCALATION_RESOLVED.value,
                related_entity_type="escalation",
                related_entity_id=escalation_id,
            )
        )

        return notifications
