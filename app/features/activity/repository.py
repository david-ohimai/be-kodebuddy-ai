from sqlmodel import Session, select

from .model import UserActivity


class ActivityRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        activity: UserActivity,
    ) -> UserActivity:
        self.session.add(activity)
        self.session.commit()
        self.session.refresh(activity)

        return activity

    def get_by_user_id(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[UserActivity]:
        statement = (
            select(UserActivity)
            .where(UserActivity.user_id == user_id)
            .order_by(UserActivity.created_at.desc())
            .limit(limit)
        )

        return list(self.session.exec(statement).all())