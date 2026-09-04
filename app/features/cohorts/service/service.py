
from fastapi import HTTPException, status

from app.features.cohorts.models.cohort_learners import CohortLearner
from app.features.cohorts.models.model import Cohort
from app.features.cohorts.repository.repository import CohortRepository
from app.features.cohorts.schema.schema import (
    CohortCreate,
    CohortUpdate,
)


class CohortService:

    def __init__(
        self,
        repository: CohortRepository,
    ):
        self.repository = repository

    def create_cohort(
        self,
        cohort_data: CohortCreate,
        admin_id: int,
    ) -> Cohort:

        if cohort_data.start_date >= cohort_data.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cohort start date must be before end date.",
            )

        return self.repository.create(
            cohort_data,
            admin_id,
        )

    def get_cohort(
        self,
        cohort_id: int,
    ) -> Cohort:

        cohort = self.repository.get_by_id(cohort_id)

        if cohort is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cohort not found.",
            )

        return cohort

    def list_cohorts(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Cohort]:

        return self.repository.get_all(
            skip,
            limit,
        )

    def update_cohort(
        self,
        cohort_id: int,
        cohort_data: CohortUpdate,
    ) -> Cohort:

        if (
            cohort_data.start_date is not None
            and cohort_data.end_date is not None
            and cohort_data.start_date >= cohort_data.end_date
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cohort start date must be before end date.",
            )

        cohort = self.repository.update(
            cohort_id,
            cohort_data,
        )

        if cohort is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cohort not found.",
            )

        return cohort


    def delete_cohort(
        self,
        cohort_id: int,
    ) -> dict:

        deleted = self.repository.delete(cohort_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cohort not found.",
            )

        return {
            "message": "Cohort successfully deleted"
        }