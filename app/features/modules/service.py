from datetime import datetime

from fastapi import HTTPException

from app.features.auth.model import User
from .model import Module
from .repository import ModuleRepository
from .schema import ModuleCreate, ModuleUpdate, ReorderModulesRequest


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

    def update_module(self, module_id: int, data: ModuleUpdate) -> Module:
        module = self.repository.get_by_id(module_id)

        if module is None:
            raise HTTPException(
                status_code=404,
                detail="Module not found",
            )

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(module, field, value)

        module.updated_at = datetime.utcnow()

        return self.repository.update(module)

    def delete_module(self, module_id: int) -> None:
        module = self.repository.get_by_id(module_id)

        if module is None:
            raise HTTPException(
                status_code=404,
                detail="Module not found",
            )

        self.repository.delete(module)

    def reorder_modules(self, data: ReorderModulesRequest) -> list[Module]:
        requested_ids = [item.id for item in data.modules]
        modules = self.repository.get_by_ids(requested_ids)

        found_ids = {module.id for module in modules}
        missing_ids = set(requested_ids) - found_ids

        if missing_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Module(s) not found: {sorted(missing_ids)}",
            )

        order_map = {item.id: item.order for item in data.modules}

        for module in modules:
            module.order = order_map[module.id]
            module.updated_at = datetime.utcnow()

        return self.repository.bulk_update_order(modules)