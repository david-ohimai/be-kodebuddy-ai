from datetime import datetime, timezone

from sqlmodel import Session, select

from app.features.assignments.model import Assignment
from app.features.assignments.schema import (
    AssignmentCreate,
    AssignmentUpdate,
)


class AssignmentRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        assignment_data: AssignmentCreate,
        created_by: int,
    ) -> Assignment:

        assignment = Assignment(
            module_id=assignment_data.module_id,
            title=assignment_data.title,
            description=assignment_data.description,
            due_date=assignment_data.due_date,
            maximum_score=assignment_data.maximum_score,
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
    ) -> list[Assignment]:

        statement = select(Assignment).where(
            Assignment.is_active == True
        )

        if module_id is not None:
            statement = statement.where(
                Assignment.module_id == module_id
            )

        return list(self.db.exec(statement).all())

    def get_assignment_by_id(
        self,
        assignment_id: int,
    ) -> Assignment | None:

        statement = select(Assignment).where(
            Assignment.id == assignment_id,
            Assignment.is_active == True,
        )

        return self.db.exec(statement).first()

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