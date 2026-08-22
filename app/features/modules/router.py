from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.auth import get_current_user
from app.core.session import get_session
from app.features.auth.model import User

from .repository import ModuleRepository
from .schema import ModuleCreate, ModuleResponse, ModuleUpdate, ReorderModulesRequest
from .service import ModuleService


router = APIRouter(
    prefix="/modules",
    tags=["Modules"],
)


def get_module_service(
    session: Session = Depends(get_session),
) -> ModuleService:
    repository = ModuleRepository(session)

    return ModuleService(repository=repository, session=session)


@router.post(
    "",
    response_model=ModuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_module(
    data: ModuleCreate,
    current_user: User = Depends(get_current_user),
    service: ModuleService = Depends(get_module_service),
):
    return service.create_module(data, current_user)

@router.get(
    "/course/{course_id}",
    response_model=list[ModuleResponse],
)
def get_course_modules(
    course_id: int,
    current_user: User = Depends(get_current_user),
    service: ModuleService = Depends(get_module_service),
):
    return service.get_modules_for_course(
        course_id,
        current_user
    )


@router.get(
    "/{module_id}",
    response_model=ModuleResponse
)
def get_module(
    module_id: int,
    current_user: User = Depends(get_current_user),
    service: ModuleService = Depends(get_module_service),
):
    return service.get_module(
        module_id,
        current_user
    )


@router.patch(
    "/reorder",
    response_model=list[ModuleResponse],
)
def reorder_modules(
    data: ReorderModulesRequest,
    current_user: User = Depends(get_current_user),
    service: ModuleService = Depends(get_module_service),
):
    return service.reorder_modules(data, current_user)


@router.patch(
    "/{module_id}",
    response_model=ModuleResponse,
)
def update_module(
    module_id: int,
    data: ModuleUpdate,
    current_user: User = Depends(get_current_user),
    service: ModuleService = Depends(get_module_service),
):
    return service.update_module(module_id, data, current_user)


@router.delete(
    "/{module_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_module(
    module_id: int,
    current_user: User = Depends(get_current_user),
    service: ModuleService = Depends(get_module_service),
):
    service.delete_module(module_id, current_user)