from fastapi import BackgroundTasks, HTTPException, status

from app.features.auth.model import User, UserRole
from app.features.lessons.repository import LessonRepository
from app.features.modules.repository import ModuleRepository
from app.features.modules.service import (
    verify_learner_course_access,
    verify_trainer_course_access,
)
from app.features.resources.model import Resource
from app.features.resources.repository import ResourceRepository
from app.features.resources.schema import (
    ResourceCreate,
    ResourceUpdate,
)

from .base_resource_service import BaseResourceService


class LessonResourceService(BaseResourceService):

    def __init__(
        self,
        repository: ResourceRepository,
        lesson_repository: LessonRepository,
        module_repository: ModuleRepository,
    ):
        super().__init__(repository)

        self.lesson_repository = lesson_repository
        self.module_repository = module_repository

    # ============ CREATE ============

    def create_resource(
        self,
        lesson_id: int,
        data: ResourceCreate,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
        file=None,
    ) -> Resource:

        self.check_can_create(current_user)

        lesson = self.lesson_repository.get_active_by_id(
            lesson_id
        )

        if lesson is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )

        module = self.module_repository.get_by_id(
            lesson.module_id
        )

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        # Trainer must have access to the course containing the lesson.
        if current_user.role == UserRole.TRAINER:
            verify_trainer_course_access(
                session=self.repository.db,
                current_user=current_user,
                course_id=module.course_id,
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

        resource = self.repository.create(
            resource_data=data,
            module_id=lesson.module_id,
            created_by=current_user.id,
            lesson_id=lesson.id,
        )

        # Schedule ingestion
        self._schedule_ingestion(resource.id, background_tasks)

        return resource

    # ============ GET ALL ============

    def get_resources(
        self,
        lesson_id: int,
        current_user: User,
    ) -> list[Resource]:

        lesson = self.get_accessible_lesson(
            lesson_id,
            current_user,
        )

        return self.repository.get_all_for_lesson(
            lesson.id
        )

    # ============ GET ONE ============

    def get_resource(
        self,
        lesson_id: int,
        resource_id: int,
        current_user: User,
    ) -> Resource:

        lesson = self.get_accessible_lesson(
            lesson_id,
            current_user,
        )

        resource = self.repository.get_by_id_for_lesson(
            resource_id=resource_id,
            lesson_id=lesson.id,
        )

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found in this lesson",
            )

        return resource

    # ============ UPDATE ============

    def update_resource(
        self,
        lesson_id: int,
        resource_id: int,
        data: ResourceUpdate,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
        file=None,
    ) -> Resource:

        resource = self.get_resource_for_management(
            lesson_id=lesson_id,
            resource_id=resource_id,
            current_user=current_user,
        )

        updated = self.update_resource_data(
            resource=resource,
            data=data,
            current_user=current_user,
            file=file,
        )

        # Schedule ingestion
        self._schedule_ingestion(updated.id, background_tasks)

        return updated

    # ============ DELETE ============

    def delete_resource(
        self,
        lesson_id: int,
        resource_id: int,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> Resource:

        resource = self.get_resource_for_management(
            lesson_id=lesson_id,
            resource_id=resource_id,
            current_user=current_user,
        )

        deleted = self.repository.delete(
            resource
        )

        # Schedule ingestion (will remove embeddings since is_active=False)
        self._schedule_ingestion(deleted.id, background_tasks)

        return deleted

    # ============ ACCESS HELPERS ============

    def get_accessible_lesson(
        self,
        lesson_id: int,
        current_user: User,
    ):

        lesson = self.lesson_repository.get_active_by_id(
            lesson_id
        )

        if lesson is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )

        module = self.module_repository.get_by_id(
            lesson.module_id
        )

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        if current_user.role == UserRole.ADMIN:
            return lesson

        if current_user.role == UserRole.TRAINER:

            verify_trainer_course_access(
                session=self.repository.db,
                current_user=current_user,
                course_id=module.course_id,
            )

            return lesson

        if current_user.role == UserRole.LEARNER:

            verify_learner_course_access(
                session=self.repository.db,
                current_user=current_user,
                course_id=module.course_id,
            )

            return lesson

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access lesson resources",
        )

    def get_resource_for_management(
        self,
        lesson_id: int,
        resource_id: int,
        current_user: User,
    ) -> Resource:

        if current_user.role not in {
            UserRole.ADMIN,
            UserRole.TRAINER,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify lesson resources",
            )

        lesson = self.get_accessible_lesson(
            lesson_id,
            current_user,
        )

        resource = self.repository.get_by_id_for_lesson(
            resource_id=resource_id,
            lesson_id=lesson.id,
        )

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found in this lesson",
            )

        return resource

    update_resource_data = BaseResourceService.update_resource