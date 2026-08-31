from datetime import datetime, timezone

from sqlmodel import Session, select

from app.features.assignments.model import Assignment
from app.features.assignments.schema import (
    AssignmentCreate,
    AssignmentUpdate,
)
from app.features.auth.model import User


class AssignmentRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        assignment_data: AssignmentCreate,
        module_id: int,
        created_by: int,
    ) -> Assignment:

        assignment = Assignment(
            **assignment_data.model_dump(),
            module_id=module_id,
            created_by=created_by,
            is_active=True,
        )

        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment

    def get_all_assignment(
        self,
        module_id: int | None = None,
    ) -> list[tuple[Assignment, str | None]]:
        """
        Assignments plus the creating trainer's display name.

        The name is joined here rather than fetched per row by the caller,
        which would be an N+1 on the list endpoint.
        """
        statement = (
            select(Assignment, User.full_name)
            .join(User, User.id == Assignment.created_by)
            .where(Assignment.is_active == True)  # noqa: E712
        )

        if module_id is not None:
            statement = statement.where(
                Assignment.module_id == module_id
            )

        return [
            (assignment, full_name)
            for assignment, full_name in self.db.exec(statement).all()
        ]

    def get_assignment_by_id(
        self,
        module_id: int,
        assignment_id: int,
    ) -> tuple[Assignment, str | None] | None:
        """One assignment plus the creating trainer's display name."""
        statement = (
            select(Assignment, User.full_name)
            .join(User, User.id == Assignment.created_by)
            .where(
                Assignment.id == assignment_id,
                Assignment.module_id == module_id,
                Assignment.is_active == True,  # noqa: E712
            )
        )

        row = self.db.exec(statement).first()

        return (row[0], row[1]) if row is not None else None

    def get_creator_name(
        self,
        user_id: int,
    ) -> str | None:
        """
        Display name for a single user.

        Used after a write, where only one assignment is in play and a join
        would mean re-querying the row we already have.
        """
        return self.db.exec(
            select(User.full_name).where(User.id == user_id)
        ).first()

    def update(
        self,
        assignment: Assignment,
        assignment_data: AssignmentUpdate,
    ) -> Assignment:

        update_data = assignment_data.model_dump(
            exclude_unset=True
        )

        for key, value in update_data.items():
            setattr(assignment, key, value)

        assignment.updated_at = datetime.now(timezone.utc)

        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment

    def delete(
        self,
        assignment: Assignment,
    ) -> Assignment:

        assignment.is_active = False
        assignment.updated_at = datetime.now(timezone.utc)

        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        return assignment