from datetime import datetime, timezone

from fastapi import HTTPException, status
from app.features.auth.model import User, UserRole
from app.features.assignments.model import Assignment
from app.features.assignments.repository import AssignmentRepository
from app.features.assignments.schema import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
)
from app.features.modules.repository import ModuleRepository


def _as_utc(value: datetime | None) -> datetime | None:
    """
    Normalise to an aware UTC datetime.

    Stored dates are timezone-aware (DateTime(timezone=True)) but a client can
    send a naive one, and comparing the two raises TypeError. Naive input is
    read as UTC rather than rejected.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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

        assignment = self.repository.create(
            data,
            module_id,
            current_user.id,
        )

        # The creator is the caller, so no extra lookup is needed here.
        return self._to_response(assignment, current_user.full_name)

    def get_assignments(
        self,
        module_id: int,
    ) -> list[AssignmentResponse]:

        return [
            self._to_response(assignment, creator_name)
            for assignment, creator_name in (
                self.repository.get_all_assignment(module_id)
            )
        ]

    def get_assignment(
        self,
        module_id: int,
        assignment_id: int,
    ) -> AssignmentResponse:

        result = self.repository.get_assignment_by_id(
            module_id,
            assignment_id,
        )

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found in this module",
            )

        assignment, creator_name = result

        return self._to_response(assignment, creator_name)


    def update_assignment(
        self,
        module_id: int,
        assignment_id: int,
        data: AssignmentUpdate,
        current_user: User,
    ) -> AssignmentResponse:

        module = self.module_repository.get_by_id(module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        result = self.repository.get_assignment_by_id(
            module_id,
            assignment_id,
        )

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found in this module",
            )

        assignment, creator_name = result

        if not self._can_manage(
            assignment,
            current_user,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to modify this assignment",
            )

        self._check_start_before_due(assignment, data)

        updated = self.repository.update(
            assignment,
            data,
        )

        return self._to_response(updated, creator_name)

    def delete_assignment(
        self,
        module_id: int,
        assignment_id: int,
        current_user: User,
    ) -> AssignmentResponse:

        module = self.module_repository.get_by_id(module_id)

        if module is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Module not found",
            )

        result = self.repository.get_assignment_by_id(
            module_id,
            assignment_id,
        )

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assignment not found in this module",
            )

        assignment, creator_name = result

        if not self._can_manage(
            assignment,
            current_user,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this assignment",
            )

        deleted = self.repository.delete(
            assignment
        )

        return self._to_response(deleted, creator_name)


    def _to_response(
        self,
        assignment: Assignment,
        creator_name: str | None,
    ) -> AssignmentResponse:
        """
        Build the API response, attaching the creating trainer's display name.

        The name lives on the response rather than being looked up by the
        client because GET /users/{id} is admin-only — a learner rendering a
        trainer byline would get a 403 on every page load.
        """
        response = AssignmentResponse.model_validate(assignment)
        response.created_by_name = creator_name

        return response

    def _check_start_before_due(
        self,
        assignment: Assignment,
        data: AssignmentUpdate,
    ) -> None:
        """
        Validate start/due ordering against the merged result of the update.

        The schema validator only sees the fields in the request; sending just
        one of the pair would otherwise slip past it and leave a stored
        assignment whose start date is after its due date.
        """
        fields = data.model_fields_set

        start = _as_utc(
            data.start_date if "start_date" in fields else assignment.start_date
        )
        due = _as_utc(
            data.due_date if "due_date" in fields else assignment.due_date
        )

        if start is not None and due is not None and start >= due:
            raise HTTPException(
                # Literal 422 rather than status.HTTP_422_*: Starlette is
                # mid-rename (UNPROCESSABLE_ENTITY -> UNPROCESSABLE_CONTENT)
                # and the constant that exists depends on the installed
                # version. The number does not move.
                status_code=422,
                detail="start_date must be earlier than due_date",
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