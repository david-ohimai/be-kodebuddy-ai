from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.auth import get_current_trainer
from app.core.session import get_session
from app.features.auth.model import User

from .repository import ModuleRepository
from .schema import ModuleCreate, ModuleResponse
from .service import ModuleService


router = APIRouter(
    prefix="/modules",
    tags=["Modules"],
)


def get_module_service(
    session: Session = Depends(get_session),
) -> ModuleService:
    repository = ModuleRepository(session)
    return ModuleService(repository)


@router.post(
    "",
    response_model=ModuleResponse,
)
def create_module(
    data: ModuleCreate,
    current_user: User = Depends(get_current_trainer),
    service: ModuleService = Depends(get_module_service),
):
    return service.create_module(data, current_user)