from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.core.auth import get_current_user
from app.core.session import get_session
from app.features.auth.model import User

from app.features.modules.repository import ModuleRepository

from app.features.resources.repository import (
    ResourceRepository,
)

from app.features.resources.schema import (
    ResourceCreate,
    ResourceResponse,
    ResourceUpdate,
)

from app.features.resources.service import (
    ResourceService,
)


router = APIRouter(
    prefix="/modules/{module_id}/resources",
    tags=["Resources"],
)


def get_resource_service(
    session: Session = Depends(get_session),
) -> ResourceService:

    repository = ResourceRepository(session)
    module_repository = ModuleRepository(session)

    return ResourceService(
        repository=repository,
        module_repository=module_repository,
    )


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource(
    module_id: int,
    data: ResourceCreate,
    current_user: User = Depends(get_current_user),
    service: ResourceService = Depends(get_resource_service),
):
    return service.create_resource(
        module_id,
        data,
        current_user,
    )


@router.get(
    "",
    response_model=list[ResourceResponse],
)
def get_all_resources(
    module_id: int,
    current_user: User = Depends(get_current_user),
    service: ResourceService = Depends(get_resource_service),
):
    return service.get_resources(
        module_id,
    )


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def get_resource_by_id(
    module_id: int,
    resource_id: int,
    current_user: User = Depends(get_current_user),
    service: ResourceService = Depends(get_resource_service),
):
    return service.get_resource(
        module_id,
        resource_id,
    )


@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def update_resource(
    module_id: int,
    resource_id: int,
    data: ResourceUpdate,
    current_user: User = Depends(get_current_user),
    service: ResourceService = Depends(get_resource_service),
):
    return service.update_resource(
        module_id,
        resource_id,
        data,
        current_user,
    )


@router.delete(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def delete_resource(
    module_id: int,
    resource_id: int,
    current_user: User = Depends(get_current_user),
    service: ResourceService = Depends(get_resource_service),
):
    return service.delete_resource(
        module_id,
        resource_id,
        current_user,
    )