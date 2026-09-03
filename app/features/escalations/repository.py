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
            existing = escalation.detail or ""
            text = response.strip()
            escalation.detail = (
                f"{existing}\n\nTrainer response: {text}".strip()
                if existing
                else f"Trainer response: {text}"
            )

        self.session.add(escalation)
        self.session.commit()
        self.session.refresh(escalation)
        return escalation
