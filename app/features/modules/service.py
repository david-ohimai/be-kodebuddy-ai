from app.features.auth.model import User

from .model import Module
from .repository import ModuleRepository
from .schema import ModuleCreate


class ModuleService:
    def __init__(self, repository: ModuleRepository):
        self.repository = repository

    def create_module(self, data: ModuleCreate, current_user: User) -> Module:
        module = Module(
            course_id=data.course_id,
            title=data.title,
            description=data.description,
            order=data.order,
            created_by=current_user.id,
        )
        return self.repository.create(module)