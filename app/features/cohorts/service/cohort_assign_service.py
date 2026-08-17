from fastapi import HTTPException

from app.features.cohorts.models.cohort_learners import CohortLearner
from app.features.cohorts.repository.cohort_assign_repo import (
    CohortAssignRepository,
)
from app.features.cohorts.repository.repository import CohortRepository


class CohortAssignService:

    def __init__(
        self,
        repository: CohortAssignRepository,
        cohort_repository: CohortRepository,
    ):
        self.repository = repository
        self.cohort_repository = cohort_repository

    def assign_learner(
        self,
        cohort_id: int,
        learner_id: int,
    ):
        cohort = self.cohort_repository.get_by_id(cohort_id)

        if cohort is None:
            raise HTTPException(
                status_code=404,
                detail="Cohort not found",
            )

        return self.repository.assign_learner(
            cohort_id,
            learner_id,
        )

    def assign_trainer(
        self,
        cohort_id: int,
        trainer_id: int,
    ):
        cohort = self.cohort_repository.get_by_id(cohort_id)

        if cohort is None:
            raise HTTPException(
                status_code=404,
                detail="Cohort not found",
            )

        return self.repository.assign_trainer(
            cohort_id,
            trainer_id,
        )

    def get_learners(
        self,
        cohort_id: int,
    ):
        return self.repository.get_learners(cohort_id)

    def get_trainers(
        self,
        cohort_id: int,
    ):
        return self.repository.get_trainers(cohort_id)

    def join_cohort(
        self,
        cohort_id: int,
        learner_id: int,
    ):
        cohort = self.cohort_repository.get_by_id(cohort_id)

        if cohort is None:
            raise HTTPException(
                status_code=404,
                detail="Cohort not found",
            )

        if not cohort.is_open:
            raise HTTPException(
                status_code=400,
                detail="This cohort is not open for registration",
            )

        existing = self.repository.get_by_cohort_and_learner(
            cohort_id,
            learner_id,
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="You are already registered for this cohort",
            )

        registration = CohortLearner(
            cohort_id=cohort_id,
            learner_id=learner_id,
        )

        return self.repository.create(registration)