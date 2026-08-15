from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.auth import (
    get_current_admin,
    get_current_user,
)
from app.core.session import get_session
from app.features.auth.model import User
from app.features.cohorts.repository import CohortRepository
from app.features.cohorts.schema import (
    CohortCreate,
    CohortResponse,
    CohortUpdate,
)
from app.features.cohorts.service import CohortService


router = APIRouter(
    prefix="/cohorts",
    tags=["Cohorts"],
)


def get_cohort_service(
    session: Session = Depends(get_session),
) -> CohortService:

    repository = CohortRepository(session)

    return CohortService(repository)

@router.post(
    "",
    response_model=CohortResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cohort(
    data: CohortCreate,
    current_admin: User = Depends(get_current_admin),
    service: CohortService = Depends(get_cohort_service),
):
    return service.create_cohort(
        data,
        admin_id=current_admin.id,
    )

@router.get(
    "",
    response_model=list[CohortResponse],
)
def get_all_cohorts(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    service: CohortService = Depends(get_cohort_service),
):
    return service.list_cohorts(
        skip,
        limit,
    )

@router.get(
    "/{cohort_id}",
    response_model=CohortResponse,
)
def get_cohort(
    cohort_id: UUID,
    current_user: User = Depends(get_current_user),
    service: CohortService = Depends(get_cohort_service),
):
    return service.get_cohort(cohort_id)


@router.patch(
    "/{cohort_id}",
    response_model=CohortResponse,
)
def update_cohort(
    cohort_id: UUID,
    data: CohortUpdate,
    current_admin: User = Depends(get_current_admin),
    service: CohortService = Depends(get_cohort_service),
):
    return service.update_cohort(
        cohort_id,
        data,
    )


@router.delete(
    "/{cohort_id}",
)
def delete_cohort(
    cohort_id: UUID,
    current_admin: User = Depends(get_current_admin),
    service: CohortService = Depends(get_cohort_service),
):
    return service.delete_cohort(cohort_id)