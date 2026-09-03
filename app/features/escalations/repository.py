from datetime import datetime, timezone

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