from datetime import datetime, timezone

from sqlalchemy import text
from sqlmodel import Session, select

from app.agent.model import Escalation


class EscalationRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_trainer(
        self,
        trainer_id: int,
        *,
        status: str | None = None,
        course_id: int | None = None,
        learner_id: int | None = None,
    ) -> list[Escalation]:
        statement = select(Escalation).where(
            (Escalation.trainer_id == trainer_id)
            | (Escalation.trainer_id.is_(None))
        )

        if status:
            statement = statement.where(Escalation.status == status)
        if course_id is not None:
            statement = statement.where(Escalation.course_id == course_id)
        if learner_id is not None:
            statement = statement.where(Escalation.learner_id == learner_id)

        statement = statement.order_by(Escalation.created_at.desc())
        return list(self.session.exec(statement).all())

    def list_for_learner(
        self,
        learner_id: int,
        *,
        status: str | None = None,
        course_id: int | None = None,
    ) -> list[Escalation]:
        """Same shape as list_for_trainer, but scoped to the learner's own
        rows instead of a trainer's assigned/unassigned queue -- what backs
        the learner's Escalations tab (GET /escalations/learner)."""
        statement = select(Escalation).where(Escalation.learner_id == learner_id)

        if status:
            statement = statement.where(Escalation.status == status)
        if course_id is not None:
            statement = statement.where(Escalation.course_id == course_id)

        statement = statement.order_by(Escalation.created_at.desc())
        return list(self.session.exec(statement).all())

    def get_by_id(self, escalation_id: int) -> Escalation | None:
        return self.session.get(Escalation, escalation_id)

    def get_by_id_with_learner(self, escalation_id: int) -> dict | None:
        """
        Fetches an escalation with the learner's full_name and email joined in.
        Returns a dict with all escalation fields plus learner_full_name and learner_email.
        """
        sql = """
            SELECT
                e.id,
                e.learner_id,
                e.course_id,
                e.module_id,
                e.assignment_id,
                e.trainer_id,
                e.question,
                e.reason,
                e.detail,
                e.draft_response,
                e.confidence_score,
                e.response,
                e.responded_at,
                e.status,
                e.created_at,
                e.updated_at,
                u.full_name AS learner_full_name,
                u.email AS learner_email
            FROM escalations e
            JOIN users u ON u.id = e.learner_id
            WHERE e.id = :escalation_id
        """

        row = self.session.execute(text(sql), {"escalation_id": escalation_id}).mappings().first()
        if row is None:
            return None
        return dict(row)

    def list_for_trainer_with_learner(
        self,
        trainer_id: int,
        *,
        status: str | None = None,
        course_id: int | None = None,
        learner_id: int | None = None,
    ) -> list[dict]:
        """
        Returns escalations for a trainer with learner full_name and email joined.
        Similar to list_for_trainer but returns dicts with learner details.
        """
        sql = """
            SELECT
                e.id,
                e.learner_id,
                e.course_id,
                e.module_id,
                e.assignment_id,
                e.trainer_id,
                e.question,
                e.reason,
                e.detail,
                e.draft_response,
                e.confidence_score,
                e.response,
                e.responded_at,
                e.status,
                e.created_at,
                e.updated_at,
                u.full_name AS learner_full_name,
                u.email AS learner_email
            FROM escalations e
            JOIN users u ON u.id = e.learner_id
            WHERE (e.trainer_id = :trainer_id OR e.trainer_id IS NULL)
        """

        params: dict[str, int | str] = {"trainer_id": trainer_id}

        if status:
            sql += " AND e.status = :status"
            params["status"] = status
        if course_id is not None:
            sql += " AND e.course_id = :course_id"
            params["course_id"] = course_id
        if learner_id is not None:
            sql += " AND e.learner_id = :learner_id"
            params["learner_id"] = learner_id

        sql += " ORDER BY e.created_at DESC"

        rows = self.session.execute(text(sql), params).mappings().all()
        return [dict(row) for row in rows]

    def list_for_learner_with_learner(
        self,
        learner_id: int,
        *,
        status: str | None = None,
        course_id: int | None = None,
    ) -> list[dict]:
        """
        Returns escalations for a learner with learner full_name and email joined.
        Similar to list_for_learner but returns dicts with learner details.
        """
        sql = """
            SELECT
                e.id,
                e.learner_id,
                e.course_id,
                e.module_id,
                e.assignment_id,
                e.trainer_id,
                e.question,
                e.reason,
                e.detail,
                e.draft_response,
                e.confidence_score,
                e.response,
                e.responded_at,
                e.status,
                e.created_at,
                e.updated_at,
                u.full_name AS learner_full_name,
                u.email AS learner_email
            FROM escalations e
            JOIN users u ON u.id = e.learner_id
            WHERE e.learner_id = :learner_id
        """

        params: dict[str, int | str] = {"learner_id": learner_id}

        if status:
            sql += " AND e.status = :status"
            params["status"] = status
        if course_id is not None:
            sql += " AND e.course_id = :course_id"
            params["course_id"] = course_id

        sql += " ORDER BY e.created_at DESC"

        rows = self.session.execute(text(sql), params).mappings().all()
        return [dict(row) for row in rows]

    def update(
        self,
        escalation: Escalation,
        *,
        status: str | None = None,
        response: str | None = None,
    ) -> Escalation:
        if status:
            escalation.status = status

        if response and response.strip():
            # Written to its own column, not appended into `detail` --
            # `detail` stays the agent's own field. Each PATCH overwrites
            # the prior reply and stamps `responded_at`, so the learner
            # always sees the trainer's latest answer, not a running blob.
            escalation.response = response.strip()
            escalation.responded_at = datetime.now(timezone.utc)

        self.session.add(escalation)
        self.session.commit()
        self.session.refresh(escalation)
        return escalation