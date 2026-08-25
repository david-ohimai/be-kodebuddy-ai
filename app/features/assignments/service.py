from fastapi import HTTPException, status
from app.features.auth.model import User, UserRole
from app.features.assignments.model import Assignment
from app.features.assignments.repository import AssignmentRepository
from app.features.assignments.schema import (
    AssignmentCreate,
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

    def create_assignment(
        self,
        module_id: int,
        data: AssignmentCreate,
        current_user: User,
    ) -> Assignment:

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

        return self.repository.create(
        data,
        module_id,
        current_user.id,
    )

    def get_assignments(
        self,
        module_id: int,
    ) -> list[Assignment]:

        return self.repository.get_all_assignment(
            module_id
        )

    def get_assignment(
        self,
        module_id: int,
        assignment_id: int,
    ) -> Assignment:

        assignment = self.repository.get_assignment_by_id(
            module_id,
            assignment_id,
        )

        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found in this module",
            )

        return assignment
    
    def update_assignment(
        self,
        module_id: int,
        assignment_id: int,
        data: AssignmentUpdate,
        current_user: User,
    ) -> Assignment:

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

        return self.repository.update(
            assignment,
            data,
        )

    def delete_assignment(
        self,
        module_id: int,
        assignment_id: int,
        current_user: User,
    ) -> Assignment:

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

        return self.repository.delete(
            assignment
        )


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