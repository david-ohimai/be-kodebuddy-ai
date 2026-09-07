from sqlmodel import Session, select

from app.features.auth.model import User
from app.features.cohorts.models.cohort_learners import CohortLearner, CohortMentor, CohortTrainer


class CohortAssignRepository:

    def __init__(self, session: Session):
        self.session = session

    def assign_learner(
        self,
        cohort_id: int,
        learner_id: int,
    ) -> CohortLearner:

        relationship = CohortLearner(
            cohort_id=cohort_id,
            learner_id=learner_id,
        )

        self.session.add(relationship)
        self.session.commit()
        self.session.refresh(relationship)

        return relationship

    def assign_trainer(
        self,
        cohort_id: int,
        trainer_id: int,
    ) -> CohortTrainer:

        relationship = CohortTrainer(
            cohort_id=cohort_id,
            trainer_id=trainer_id,
        )

        self.session.add(relationship)
        self.session.commit()
        self.session.refresh(relationship)

        return relationship

    def get_learners(
        self,
        cohort_id: int,
    ) -> list[CohortLearner]:

        statement = select(CohortLearner).where(
            CohortLearner.cohort_id == cohort_id
        )

        return list(self.session.exec(statement).all())

    def get_trainers(
        self,
        cohort_id: int,
    ) -> list[CohortTrainer]:

        statement = select(CohortTrainer).where(
            CohortTrainer.cohort_id == cohort_id
        )

        return list(self.session.exec(statement).all())

    def assign_mentor(
        self, 
        cohort_id: int,
        mentor_id: int,
    ) -> CohortMentor:
        relationship = CohortMentor(
            cohort_id=cohort_id,
            mentor_id=mentor_id,
        )

        self.session.add(relationship)
        self.session.commit()
        self.session.refresh(relationship)

        return relationship

    def get_mentor_assignment(
        self,
        cohort_id: int,
        mentor_id: int,
    ) -> CohortMentor | None:
        statement = select(CohortMentor).where(
            CohortMentor.cohort_id == cohort_id,
            CohortMentor.mentor_id == mentor_id,
        )
        return self.session.exec(statement).first()


    def update_mentor_assignment(
        self,
        assignment: CohortMentor,
    ) -> CohortMentor:
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)
        return assignment

    def get_mentors(
        self,
        cohort_id: int,
    ) -> list[CohortMentor]:

        statement = select(CohortMentor).where(
            CohortMentor.cohort_id == cohort_id
        )

        return list(self.session.exec(statement).all())


    def create(
        self,
        registration: CohortLearner,
    ) -> CohortLearner:

        self.session.add(registration)
        self.session.commit()
        self.session.refresh(registration)

        return registration

    def get_by_cohort_and_learner(
        self,
        cohort_id: int,
        learner_id: int,
    ) -> CohortLearner | None:

        return self.session.exec(
            select(CohortLearner).where(
                CohortLearner.cohort_id == cohort_id,
                CohortLearner.learner_id == learner_id,
            )
        ).first()

    def get_user_by_id(
        self,
        user_id: int,
    ) -> User | None:
        return self.session.get(User, user_id)

    def get_learner_assignment(
        self,
        cohort_id: int,
        learner_id: int,
    ) -> CohortLearner | None:
        statement = select(CohortLearner).where(
            CohortLearner.cohort_id == cohort_id,
            CohortLearner.learner_id == learner_id,
        )

        return self.session.exec(statement).first()

    def get_trainer_assignment(
        self,
        cohort_id: int,
        trainer_id: int,
    ) -> CohortTrainer | None:
        statement = select(CohortTrainer).where(
            CohortTrainer.cohort_id == cohort_id,
            CohortTrainer.trainer_id == trainer_id,
        )

        return self.session.exec(statement).first()

    def update_learner_assignment(
        self,
        assignment: CohortLearner,
    ) -> CohortLearner:
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)

        return assignment

    def update_trainer_assignment(
        self,
        assignment: CohortTrainer,
    ) -> CohortTrainer:
        self.session.add(assignment)
        self.session.commit()
        self.session.refresh(assignment)

        return assignment
