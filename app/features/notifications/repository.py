from sqlmodel import Session, select

from app.features.notifications.model import Notification


class NotificationRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        user_id: int,
        title: str,
        message: str,
        notification_type: str,
        related_entity_type: str | None = None,
        related_entity_id: int | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        self.session.add(notification)
        self.session.commit()
        self.session.refresh(notification)
        return notification

    def list_for_user(self, user_id: int, *, limit: int = 50) -> list[Notification]:
        statement = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def mark_read(self, notification_id: int, user_id: int, *, is_read: bool = True) -> Notification | None:
        notification = self.session.get(Notification, notification_id)
        if notification is None or notification.user_id != user_id:
            return None
        notification.is_read = is_read
        self.session.add(notification)
        self.session.commit()
        self.session.refresh(notification)
        return notification

    def unread_count(self, user_id: int) -> int:
        statement = select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        return len(list(self.session.exec(statement).all()))
