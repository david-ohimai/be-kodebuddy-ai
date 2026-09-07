from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.auth import get_current_admin
from app.core.session import get_session
from app.features.auth.model import User

from app.features.cohorts.repository.cohort_assign_repo import CohortAssignRepository
from app.features.cohorts.repository.repository import CohortRepository
from app.features.cohorts.schema.schema import (
    AssignLearnerRequest,
    AssignTrainerRequest,
    AssignMentorRequest,
    CohortLearnerResponse,
    CohortTrainerResponse,
    CohortMentorResponse,
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

@router.post(
    "/{cohort_id}/mentor",
    response_model=CohortMentorResponse,
)
def assign_mentor(
    cohort_id: int,
    data: AssignMentorRequest,
    current_admin: User = Depends(get_current_admin),
    service: CohortAssignService = Depends(
        get_cohort_assign_service
    ),
):
    return service.assign_mentor(
        cohort_id,
        data.mentor_id,
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

@router.get(
    "/{cohort_id}/mentors",
    response_model=list[CohortMentorResponse],
)
def get_cohort_mentors(
    cohort_id: int,
    current_admin: User = Depends(get_current_admin),
    service: CohortAssignService = Depends(get_cohort_assign_service),
):

    return service.get_mentors(cohort_id)