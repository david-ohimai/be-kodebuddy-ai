from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    UploadFile,
    status,
)
from sqlmodel import Session

from app.core.auth import get_current_user
from app.core.session import get_session
from app.features.auth.model import User
from app.features.modules.repository import ModuleRepository
from app.features.resources.model import ResourceType
from app.features.resources.repository import ResourceRepository
from app.features.resources.schema import (
    ResourceCreate,
    ResourceResponse,
    ResourceUpdate,
)

from app.features.resources.services.module_resource_service import (
    ModuleResourceService,
)


router = APIRouter(
    prefix="/modules/{module_id}/resources",
    tags=["Module Resources"],
)


def get_module_resource_service(
    session: Session = Depends(get_session),
) -> ModuleResourceService:

    repository = ResourceRepository(session)
    module_repository = ModuleRepository(session)

    return ModuleResourceService(
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
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str | None = Form(default=None),
    type: ResourceType = Form(...),
    url: str | None = Form(default=None),
    content: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    service: ModuleResourceService = Depends(
        get_module_resource_service
    ),
):

    data = ResourceCreate(
        title=title,
        description=description,
        type=type,
        url=url,
        content=content,
    )

    return service.create_resource(
        module_id=module_id,
        data=data,
        current_user=current_user,
        background_tasks=background_tasks,
        file=file,
    )


@router.get(
    "",
    response_model=list[ResourceResponse],
)
def get_all_resources(
    module_id: int,
    current_user: User = Depends(get_current_user),
    service: ModuleResourceService = Depends(
        get_module_resource_service
    ),
):

    return service.get_resources(
        module_id=module_id,
    )


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def get_resource(
    module_id: int,
    resource_id: int,
    current_user: User = Depends(get_current_user),
    service: ModuleResourceService = Depends(
        get_module_resource_service
    ),
):

    return service.get_resource(
        module_id=module_id,
        resource_id=resource_id,
    )


@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def update_resource(
    module_id: int,
    resource_id: int,
    background_tasks: BackgroundTasks,
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    type: ResourceType | None = Form(default=None),
    url: str | None = Form(default=None),
    content: str | None = Form(default=None),
    is_active: bool | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    service: ModuleResourceService = Depends(
        get_module_resource_service
    ),
):

    data = ResourceUpdate(
        title=title,
        description=description,
        type=type,
        url=url,
        content=content,
        is_active=is_active,
    )

    return service.update_resource(
        module_id=module_id,
        resource_id=resource_id,
        data=data,
        current_user=current_user,
        background_tasks=background_tasks,
        file=file,
    )


@router.delete(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def delete_resource(
    module_id: int,
    resource_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    service: ModuleResourceService = Depends(
        get_module_resource_service
    ),
):

    return service.delete_resource(
        module_id=module_id,
        resource_id=resource_id,
        current_user=current_user,
        background_tasks=background_tasks,
    )