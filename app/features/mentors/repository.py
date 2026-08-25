from sqlmodel import Session, select

from app.features.auth.model import User

from .model import MentorLearner


class MentorRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_assignment(self, assignment: MentorLearner) -> MentorLearner:
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def get_assignment(self, mentor_id: int, learner_id: int) -> MentorLearner | None:
        statement = select(MentorLearner).where(
            MentorLearner.mentor_id == mentor_id,
            MentorLearner.learner_id == learner_id,
        )
        return self.session.exec(statement).first()

    def get_assigned_learners(self, mentor_id: int) -> list[tuple[MentorLearner, User]]:
        statement = (
            select(MentorLearner, User)
            .where(MentorLearner.mentor_id == mentor_id)
            .where(User.id == MentorLearner.learner_id)
        )
        return list(self.session.exec(statement))