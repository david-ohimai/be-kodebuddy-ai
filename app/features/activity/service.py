from .model import ActivityType, UserActivity
from .repository import ActivityRepository


class ActivityService:
    def __init__(
        self,
        repository: ActivityRepository,
    ):
        self.repository = repository

    def record(
        self,
        user_id: int,
        activity_type: ActivityType,
        title: str,
        description: str | None = None,
    ) -> UserActivity:
        activity = UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            title=title,
            description=description,
        )

        return self.repository.create(activity)

    def get_user_activity(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[UserActivity]:
        return self.repository.get_by_user_id(
            user_id=user_id,
            limit=limit,
        )

    def get_admin_activity(
        self,
        limit: int = 20,
    ) -> list[UserActivity]:
        return self.repository.get_recent(
            limit=limit,
        )

    def get_trainer_activity(
        self,
        trainer_id: int,
        limit: int = 20,
    ) -> list[UserActivity]:
        return self.repository.get_by_trainer_id(
            trainer_id=trainer_id,
            limit=limit,
        )

    def get_mentor_activity(
        self,
        mentor_id: int,
        limit: int = 20,
    ) -> list[UserActivity]:
        return self.repository.get_by_mentor_id(
            mentor_id=mentor_id,
            limit=limit,
        )