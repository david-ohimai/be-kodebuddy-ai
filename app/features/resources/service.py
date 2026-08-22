from fastapi import HTTPException, status

from app.features.auth.model import User, UserRole
from app.features.resources.model import Resource
from app.features.resources.repository import ResourceRepository
from app.features.resources.schema import (
    ResourceCreate,
    ResourceUpdate,
)
from app.features.modules.repository import ModuleRepository


class ResourceService:

    def __init__(
        self,
        repository: ResourceRepository,
        module_repository: ModuleRepository,
    ):
        self.repository = repository
        self.module_repository = module_repository

    def create_resource(
        self,
        module_id: int,
        data: ResourceCreate,
        current_user: User,
    ) -> Resource:

        if current_user.role not in {
            UserRole.ADMIN,
            UserRole.TRAINER,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins and trainers can create resources",
            )

        module = self.module_repository.get_by_id(
            module_id
        )

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        return self.repository.create(
            data,
            module_id,
            current_user.id,
        )

    def get_resources(
        self,
        module_id: int,
    ) -> list[Resource]:

        module = self.module_repository.get_by_id(
            module_id
        )

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        return self.repository.get_all(
            module_id
        )

    def get_resource(
        self,
        module_id: int,
        resource_id: int,
    ) -> Resource:

        module = self.module_repository.get_by_id(
            module_id
        )

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        resource = self.repository.get_by_id(
            resource_id,
            module_id,
        )

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found in this module",
            )

        return resource

    def update_resource(
        self,
        module_id: int,
        resource_id: int,
        data: ResourceUpdate,
        current_user: User,
    ) -> Resource:

        resource = self.get_resource(
            module_id,
            resource_id,
        )

        if not self._can_manage(
            resource,
            current_user,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this resource",
            )

        return self.repository.update(
            resource,
            data,
        )

    def delete_resource(
        self,
        module_id: int,
        resource_id: int,
        current_user: User,
    ) -> Resource:

        resource = self.get_resource(
            module_id,
            resource_id,
        )

        if not self._can_manage(
            resource,
            current_user,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this resource",
            )

        return self.repository.delete(
            resource
        )

    def _can_manage(
        self,
        resource: Resource,
        current_user: User,
    ) -> bool:

        if current_user.role == UserRole.ADMIN:
            return True

        if (
            current_user.role == UserRole.TRAINER
            and resource.created_by == current_user.id
        ):
            return True

        return False