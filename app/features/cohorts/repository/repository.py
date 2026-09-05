from datetime import datetime, timezone

from sqlmodel import Session, select

from app.features.cohorts.models.cohort_learners import CohortLearner
from app.features.cohorts.models.model import Cohort
from app.features.cohorts.schema.schema import (
    CohortCreate,
    CohortUpdate,
)


class CohortRepository:

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        cohort_data: CohortCreate,
        admin_id: int,
    ) -> Cohort:

        if cohort_data.is_open:
            self.close_all_open_cohorts()

        cohort = Cohort(
            **cohort_data.model_dump(),
            created_by=admin_id,
        )

        self.session.add(cohort)
        self.session.commit()
        self.session.refresh(cohort)

        return cohort

    def get_by_id(
        self,
        cohort_id: int,
    ) -> Cohort | None:

        return self.session.get(
            Cohort,
            cohort_id,
        )

    def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Cohort]:

        return list(
            self.session.exec(
                select(Cohort)
                .offset(skip)
                .limit(limit)
            ).all()
        )



    def update(
        self,
        cohort_id: int,
        cohort_data: CohortUpdate,
    ) -> Cohort | None:

        cohort = self.get_by_id(cohort_id)

        if cohort is None:
            return None

        update_data = cohort_data.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(cohort, field, value)

        cohort.updated_at = datetime.now(timezone.utc)

        self.session.add(cohort)
        self.session.commit()
        self.session.refresh(cohort)

        return cohort

    def delete(
        self,
        cohort_id: int,
    ) -> bool:

        cohort = self.get_by_id(cohort_id)

        if cohort is None:
            return False

        self.session.delete(cohort)
        self.session.commit()

        return True

    def get_current_cohort(self) -> Cohort | None:
        statement = (
            select(Cohort)
            .where(Cohort.is_open == True)
            .order_by(Cohort.id.desc())
        )

        return self.session.exec(statement).first()

    def close_other_cohorts(self, cohort_id: int):
        statement = select(Cohort).where(
            Cohort.id != cohort_id,
            Cohort.is_open == True,
        )

        cohorts = self.session.exec(statement).all()

        for cohort in cohorts:
            cohort.is_open = False
            cohort.updated_at = datetime.now(timezone.utc)
            self.session.add(cohort)

    def close_all_open_cohorts(self):
        statement = select(Cohort).where(
            Cohort.is_open == True,
        )

        cohorts = self.session.exec(statement).all()

        for cohort in cohorts:
            cohort.is_open = False
            cohort.updated_at = datetime.now(timezone.utc)
            self.session.add(cohort)