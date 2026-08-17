from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.auth import get_current_admin, get_current_learner
from app.core.session import get_session
from app.features.auth.model import User

from app.features.cohorts.repository.cohort_assign_repo import CohortAssignRepository
from app.features.cohorts.repository.repository import CohortRepository
from app.features.cohorts.schema.schema import (
    AssignLearnerRequest,
    AssignTrainerRequest,
    CohortLearnerResponse,
    CohortTrainerResponse,
)
from app.features.cohorts.service.cohort_assign_service import (
    CohortAssignService,
)


router = APIRouter(
    prefix="/assign-cohorts",
    tags=["Assign-Cohorts"],
)


def get_cohort_assign_service(
    session: Session = Depends(get_session),
) -> CohortAssignService:

    repository = CohortAssignRepository(session)
    cohort_repository = CohortRepository(session)

    return CohortAssignService(
        repository,
        cohort_repository,
    )

@router.post(
    "/{cohort_id}/learner",
    response_model=CohortLearnerResponse,
)
def assign_learner(
    cohort_id: int,
    data: AssignLearnerRequest,
    current_admin: User = Depends(get_current_admin),
    service: CohortAssignService = Depends(
        get_cohort_assign_service
    ),
):
    return service.assign_learner(
        cohort_id,
        data.learner_id,
    )

@router.post(
    "/{cohort_id}/trainer",
    response_model=CohortTrainerResponse,
)
def assign_trainer(
    cohort_id: int,
    data: AssignTrainerRequest,
    current_admin: User = Depends(get_current_admin),
    service: CohortAssignService = Depends(
        get_cohort_assign_service
    ),
):
    return service.assign_trainer(
        cohort_id,
        data.trainer_id,
    )

@router.get(
    "/{cohort_id}/learners",
    response_model=list[CohortLearnerResponse],
)
def get_cohort_learners(
    cohort_id: int,
    current_admin: User = Depends(get_current_admin),
    service: CohortAssignService = Depends(get_cohort_assign_service),
):
    return service.get_learners(cohort_id)


@router.get(
    "/{cohort_id}/trainers",
    response_model=list[CohortTrainerResponse],
)
def get_cohort_trainers(
    cohort_id: int,
    current_admin: User = Depends(get_current_admin),
    service: CohortAssignService = Depends(get_cohort_assign_service),
):
    return service.get_trainers(cohort_id)


@router.post(
    "/{cohort_id}/join",
    response_model=CohortLearnerResponse,
)
def join_cohort(
    cohort_id: int,
    current_user: User = Depends(get_current_learner),
    service: CohortAssignService = Depends(
        get_cohort_assign_service
    ),
):
    return service.join_cohort(
        cohort_id=cohort_id,
        learner_id=current_user.id,
    )