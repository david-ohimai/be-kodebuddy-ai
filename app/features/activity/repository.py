from sqlmodel import Session, select

from app.features.courses.model import CourseLearner, CourseTrainer
from app.features.mentors.model import MentorLearner

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

    def get_recent(
        self,
        limit: int = 20,
    ) -> list[UserActivity]:
        statement = (
            select(UserActivity)
            .order_by(UserActivity.created_at.desc())
            .limit(limit)
        )

        return list(self.session.exec(statement).all())

    def get_by_trainer_id(
        self,
        trainer_id: int,
        limit: int = 20,
    ) -> list[UserActivity]:
        statement = (
            select(UserActivity)
            .join(
                CourseLearner,
                CourseLearner.learner_id == UserActivity.user_id,
            )
            .join(
                CourseTrainer,
                CourseTrainer.course_id == CourseLearner.course_id,
            )
            .where(
                CourseTrainer.trainer_id == trainer_id,
            )
            .order_by(UserActivity.created_at.desc())
            .limit(limit)
        )

        return list(self.session.exec(statement).all())

    def get_by_mentor_id(
        self,
        mentor_id: int,
        limit: int = 20,
    ) -> list[UserActivity]:
        statement = (
            select(UserActivity)
            .join(
                MentorLearner,
                MentorLearner.learner_id == UserActivity.user_id,
            )
            .where(
                MentorLearner.mentor_id == mentor_id,
            )
            .order_by(UserActivity.created_at.desc())
            .limit(limit)
        )

        return list(self.session.exec(statement).all())