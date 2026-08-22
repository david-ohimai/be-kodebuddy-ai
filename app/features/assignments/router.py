from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.auth import (
    get_current_admin,
    get_current_user,
)
from app.core.session import get_session
from app.features.auth.model import User

from app.features.assignments.repository import (
    AssignmentRepository,
)
from app.features.assignments.schema import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
)
from app.features.assignments.service import (
    AssignmentService,
)
from app.features.modules.repository import ModuleRepository


router = APIRouter(
    prefix="/modules/{module_id}/assignments",
    tags=["Assignments"],
)


def get_assignment_service(
    session: Session = Depends(get_session),
) -> AssignmentService:

    repository = AssignmentRepository(session)
    module_repository = ModuleRepository(session)

    return AssignmentService(
        repository=repository,
        module_repository=module_repository,
    )


@router.post(
    "",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment(
    module_id: int,
    data: AssignmentCreate,
    current_user: User = Depends(get_current_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    return service.create_assignment(
        module_id,
        data,
        current_user,
    )


@router.get(
    "",
    response_model=list[AssignmentResponse],
)
def get_all_assignments(
    module_id: int,
    current_user: User = Depends(get_current_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    return service.get_assignments(
        module_id,
    )


@router.get(
    "/{assignment_id}",
    response_model=AssignmentResponse,
)
def get_assignment_by_id(
    module_id: int,
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    return service.get_assignment(
        module_id,
        assignment_id,
    )


@router.patch(
    "/{assignment_id}",
    response_model=AssignmentResponse,
)
def update_assignment(
    module_id: int,
    assignment_id: int,
    data: AssignmentUpdate,
    current_user: User = Depends(get_current_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    return service.update_assignment(
        module_id,
        assignment_id,
        data,
        current_user,
    )


@router.delete(
    "/{assignment_id}",
    response_model=AssignmentResponse,
)

def delete_assignment(
    module_id: int,
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    service: AssignmentService = Depends(get_assignment_service),
):
    return service.delete_assignment(
        module_id,
        assignment_id,
        current_user,
    )