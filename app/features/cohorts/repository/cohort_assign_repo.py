from sqlmodel import Session, select, func

from app.features.cohorts.models.cohort_learners import CohortLearner, CohortTrainer



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