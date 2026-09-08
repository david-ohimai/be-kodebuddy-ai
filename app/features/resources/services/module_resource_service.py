from fastapi import HTTPException, status

from app.features.auth.model import User
from app.features.modules.repository import ModuleRepository
from app.features.resources.model import Resource
from app.features.resources.repository import ResourceRepository
from app.features.resources.schema import (
    ResourceCreate,
    ResourceUpdate,
)

from .base_resource_service import BaseResourceService


class ModuleResourceService(BaseResourceService):

    def __init__(
        self,
        repository: ResourceRepository,
        module_repository: ModuleRepository,
    ):
        super().__init__(repository)

        self.module_repository = module_repository

     # ============ CREATE ============

    def create_resource(
        self,
        module_id: int,
        data: ResourceCreate,
        current_user: User,
        file=None,
    ) -> Resource:

        self.check_can_create(
            current_user
        )

        module = self.module_repository.get_by_id(
            module_id
        )

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        self.validate_resource_data(
            resource_type=data.type,
            url=data.url,
            content=data.content,
            file=file,
        )

        data = self.prepare_create_data(
            data=data,
            file=file,
        )

        return self.repository.create(
            resource_data=data,
            module_id=module_id,
            created_by=current_user.id,
            lesson_id=None,
        )

     # ============ GET ALL ============

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

     # ============ GET ONE ============

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
            resource_id=resource_id,
            module_id=module_id,
        )

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found in this module",
            )

        return resource
    
    # ============ UPDATE ============

    def update_resource(
        self,
        module_id: int,
        resource_id: int,
        data: ResourceUpdate,
        current_user: User,
        file=None,
    ) -> Resource:

        resource = self.get_resource(
            module_id=module_id,
            resource_id=resource_id,
        )

        return self.update_resource_data(
            resource=resource,
            data=data,
            current_user=current_user,
            file=file,
        )

     # ============ DELETE ============

    def delete_resource(
        self,
        module_id: int,
        resource_id: int,
        current_user: User,
    ) -> Resource:

        resource = self.get_resource(
            module_id=module_id,
            resource_id=resource_id,
        )

        self.check_can_manage(
            resource,
            current_user,
        )

        return self.repository.delete(
            resource
        )

    # Shared update implementation from BaseResourceService
    update_resource_data = BaseResourceService.update_resource