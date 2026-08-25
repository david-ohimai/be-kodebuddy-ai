from sqlmodel import Session, select

from app.features.auth.model import User

from .model import MentorLearner
from .model import MentorCheckIn


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


    def create_check_in(self, check_in: MentorCheckIn) -> MentorCheckIn:
        self.session.add(check_in)
        self.session.commit()
        self.session.refresh(check_in)
        return check_in

    def get_check_in_by_id(self, check_in_id: int) -> MentorCheckIn | None:
        return self.session.get(MentorCheckIn, check_in_id)

    def get_check_ins_for_mentor(self, mentor_id: int) -> list[MentorCheckIn]:
        statement = select(MentorCheckIn).where(
            MentorCheckIn.mentor_id == mentor_id
        )
        return list(self.session.exec(statement))

    def get_check_ins_for_learner(
        self, mentor_id: int, learner_id: int
    ) -> list[MentorCheckIn]:
        statement = select(MentorCheckIn).where(
            MentorCheckIn.mentor_id == mentor_id,
            MentorCheckIn.learner_id == learner_id,
        )
        return list(self.session.exec(statement))

    def update_check_in(self, check_in: MentorCheckIn) -> MentorCheckIn:
        self.session.add(check_in)
        self.session.commit()
        self.session.refresh(check_in)
        return check_in