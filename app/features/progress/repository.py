from sqlmodel import Session, select

from .model import UserProgress


class ProgressRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, progress: UserProgress) -> UserProgress:
        self.session.add(progress)
        self.session.commit()
        self.session.refresh(progress)
        return progress

    def update(self, progress: UserProgress) -> UserProgress:
        self.session.add(progress)
        self.session.commit()
        self.session.refresh(progress)
        return progress

    def get_by_learner_and_lesson(
        self,
        learner_id: int,
        lesson_id: int,
    ) -> UserProgress | None:
        statement = select(UserProgress).where(
            UserProgress.learner_id == learner_id,
            UserProgress.lesson_id == lesson_id,
        )
        return self.session.exec(statement).first()

    def get_by_learner_and_lessons(
        self,
        learner_id: int,
        lesson_ids: list[int],
    ) -> list[UserProgress]:
        if not lesson_ids:
            return []

        statement = select(UserProgress).where(
            UserProgress.learner_id == learner_id,
            UserProgress.lesson_id.in_(lesson_ids),
        )
        return list(self.session.exec(statement))