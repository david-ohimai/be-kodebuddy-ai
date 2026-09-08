from fastapi import (
    APIRouter,
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
from app.features.lessons.repository import LessonRepository
from app.features.modules.repository import ModuleRepository
from app.features.resources.model import ResourceType
from app.features.resources.repository import ResourceRepository
from app.features.resources.schema import (
    ResourceCreate,
    ResourceResponse,
    ResourceUpdate,
)

from app.features.resources.services.lesson_resource_service import (
    LessonResourceService,
)


router = APIRouter(
    prefix="/lessons/{lesson_id}/resources",
    tags=["Lesson Resources"],
)


def get_lesson_resource_service(
    session: Session = Depends(get_session),
) -> LessonResourceService:

    repository = ResourceRepository(session)
    lesson_repository = LessonRepository(session)
    module_repository = ModuleRepository(session)

    return LessonResourceService(
        repository=repository,
        lesson_repository=lesson_repository,
        module_repository=module_repository,
    )

@router.post(
    "",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource(
    lesson_id: int,
    title: str = Form(...),
    description: str | None = Form(default=None),
    type: ResourceType = Form(...),
    url: str | None = Form(default=None),
    content: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    current_user: User = Depends(
        get_current_user
    ),
    service: LessonResourceService = Depends(
        get_lesson_resource_service
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
        lesson_id=lesson_id,
        data=data,
        current_user=current_user,
        file=file,
    )

@router.get(
    "",
    response_model=list[ResourceResponse],
)
def get_lesson_resources(
    lesson_id: int,

    current_user: User = Depends(
        get_current_user
    ),

    service: LessonResourceService = Depends(
        get_lesson_resource_service
    ),
):

    return service.get_resources(
        lesson_id=lesson_id,
        current_user=current_user,
    )

@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def get_lesson_resource(
    lesson_id: int,
    resource_id: int,

    current_user: User = Depends(
        get_current_user
    ),

    service: LessonResourceService = Depends(
        get_lesson_resource_service
    ),
):

    return service.get_resource(
        lesson_id=lesson_id,
        resource_id=resource_id,
        current_user=current_user,
    )

@router.patch(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def update_lesson_resource(
    lesson_id: int,
    resource_id: int,
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    type: ResourceType | None = Form(default=None),
    url: str | None = Form(default=None),
    content: str | None = Form(default=None),
    is_active: bool | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    service: LessonResourceService = Depends(
        get_lesson_resource_service
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
        lesson_id=lesson_id,
        resource_id=resource_id,
        data=data,
        current_user=current_user,
        file=file,
    )

@router.delete(
    "/{resource_id}",
    response_model=ResourceResponse,
)
def delete_lesson_resource(
    lesson_id: int,
    resource_id: int,
    current_user: User = Depends(get_current_user),
    service: LessonResourceService = Depends(
        get_lesson_resource_service
    ),
):

    return service.delete_resource(
        lesson_id=lesson_id,
        resource_id=resource_id,
        current_user=current_user,
    )