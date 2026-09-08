from datetime import datetime
from fastapi import BackgroundTasks, HTTPException, status
from app.features.auth.model import User, UserRole
from app.features.assignments.model import Assignment
from app.features.assignments.repository import AssignmentRepository
from app.features.assignments.schema import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
)
from app.features.modules.repository import ModuleRepository


class AssignmentService:

    def __init__(
        self,
        repository: AssignmentRepository,
        module_repository: ModuleRepository,
    ):
        self.repository = repository
        self.module_repository = module_repository

    # ============ INGESTION SCHEDULING ============

    def _schedule_ingestion(
        self,
        assignment_id: int,
        background_tasks: BackgroundTasks | None,
    ) -> None:
        """Schedules a background task to sync this assignment's embeddings."""
        from app.agent.ingestion import sync_assignment_embeddings

        if background_tasks is not None:
            background_tasks.add_task(sync_assignment_embeddings, assignment_id)
            return

        try:
            sync_assignment_embeddings(assignment_id)
        except Exception:  # noqa: BLE001 -- never let ingestion break the API call
            import logging
            logger = logging.getLogger("kodebuddy.assignments.service")
            logger.exception(
                "Inline ingestion failed for assignment_id=%s", assignment_id
            )

    def _get_assignment_response(
        self,
        assignment: Assignment,
    ) -> AssignmentResponse:

        return AssignmentResponse(
            id=assignment.id,
            module_id=assignment.module_id,
            title=assignment.title,
            description=assignment.description,
            instructions=assignment.instructions,
            requirements=assignment.requirements,
            start_date=assignment.start_date,
            due_date=assignment.due_date,
            maximum_score=assignment.maximum_score,
            created_by=assignment.created_by,
            created_by_name=self.repository.get_creator_name(
                assignment.created_by
            ),
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
            is_active=assignment.is_active,
        )

    def _validate_dates(
        self,
        start_date: datetime,
        due_date: datetime,
    ) -> None:

        if start_date >= due_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before due date",
            )

    def create_assignment(
        self,
        module_id: int,
        data: AssignmentCreate,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> AssignmentResponse:

        if current_user.role not in {
            UserRole.ADMIN,
            UserRole.TRAINER,
        }:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins and trainers can create assignments",
            )

        module = self.module_repository.get_by_id(
            module_id
        )

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        self._validate_dates(data.start_date, data.due_date)

        assignment = self.repository.create(
            data,
            module_id,
            current_user.id,
        )

        # Schedule ingestion
        self._schedule_ingestion(assignment.id, background_tasks)

        return self._get_assignment_response(assignment)

    def get_assignments(
        self,
        module_id: int,
    ) -> list[AssignmentResponse]:

        assignments = self.repository.get_all_assignment(
            module_id
        )

        return [
            self._get_assignment_response(assignment)
            for assignment in assignments
        ]

    def get_assignment(
        self,
        module_id: int,
        assignment_id: int,
    ) -> AssignmentResponse:

        assignment = self.repository.get_assignment_by_id(
            module_id,
            assignment_id,
        )

        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found in this module",
            )

        return self._get_assignment_response(assignment)

    def update_assignment(
        self,
        module_id: int,
        assignment_id: int,
        data: AssignmentUpdate,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> AssignmentResponse:

        module = self.module_repository.get_by_id(module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        assignment = self.repository.get_assignment_by_id(
            module_id,
            assignment_id,
        )

        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found in this module",
            )

        if not self._can_manage(
            assignment,
            current_user,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this assignment",
            )

        start_date = (
            data.start_date
            if data.start_date is not None
            else assignment.start_date
        )

        due_date = (
            data.due_date
            if data.due_date is not None
            else assignment.due_date
        )

        self._validate_dates(
            start_date,
            due_date,
        )

        updated_assignment = self.repository.update(
            assignment,
            data,
        )

        # Schedule ingestion
        self._schedule_ingestion(updated_assignment.id, background_tasks)

        return self._get_assignment_response(updated_assignment)

    def delete_assignment(
        self,
        module_id: int,
        assignment_id: int,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> AssignmentResponse:

        module = self.module_repository.get_by_id(module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        assignment = self.repository.get_assignment_by_id(
            module_id,
            assignment_id,
        )

        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found in this module",
            )

        if not self._can_manage(
            assignment,
            current_user,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this assignment",
            )

        deleted_assignment = self.repository.delete(
            assignment
        )

        # Schedule ingestion (will remove embeddings since is_active=False)
        self._schedule_ingestion(deleted_assignment.id, background_tasks)

        return self._get_assignment_response(deleted_assignment)

    def _can_manage(
        self,
        assignment: Assignment,
        current_user: User,
    ) -> bool:

        if current_user.role == UserRole.ADMIN:
            return True

        if (
            current_user.role == UserRole.TRAINER
            and assignment.created_by == current_user.id
        ):
            return True

        return False