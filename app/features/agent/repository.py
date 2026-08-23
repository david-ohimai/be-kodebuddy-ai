from sqlmodel import Session, func, select

from .model import ChatRole, ConversationHistory, QueryLog


class ConversationHistoryRepository:
    """
    Read/write access to `conversation_history`.

    Scoped to a single learner at construction time, matching the RBAC
    pattern in app/agent/repository.py (Dev B): a caller physically cannot
    read or write another learner's history through this class.
    """

    def __init__(self, session: Session, learner_id: int) -> None:
        self.session = session
        self.learner_id = int(learner_id)

    def add_turn(
        self,
        *,
        course_id: int,
        module_id: int | None,
        role: ChatRole,
        message: str,
    ) -> ConversationHistory:
        turn = ConversationHistory(
            learner_id=self.learner_id,
            course_id=course_id,
            module_id=module_id,
            role=role,
            message=message,
        )
        self.session.add(turn)
        self.session.commit()
        self.session.refresh(turn)
        return turn

    def add_exchange(
        self,
        *,
        course_id: int,
        module_id: int | None,
        question: str,
        final_response: str,
    ) -> None:
        """Convenience wrapper: writes the learner's question and the
        agent's final_response as two turns in one call, which is the
        common case after a single graph.invoke()."""
        self.session.add(
            ConversationHistory(
                learner_id=self.learner_id,
                course_id=course_id,
                module_id=module_id,
                role=ChatRole.USER,
                message=question,
            )
        )
        self.session.add(
            ConversationHistory(
                learner_id=self.learner_id,
                course_id=course_id,
                module_id=module_id,
                role=ChatRole.ASSISTANT,
                message=final_response,
            )
        )
        self.session.commit()

    def get_recent(
        self,
        *,
        course_id: int,
        module_id: int | None = None,
        limit: int = 6,
    ) -> list[ConversationHistory]:
        """
        Returns the most recent `limit` turns, oldest first — the order the
        graph's prompt builders expect (see graph/utils.py callers in
        nodes.py::reason).

        module_id is deliberately NOT filtered on: chat_history is meant to
        carry conversational context across a course, not just within one
        module, so a module-scoped question can still see a prior turn asked
        against a different module in the same course.
        """
        statement = (
            select(ConversationHistory)
            .where(ConversationHistory.learner_id == self.learner_id)
            .where(ConversationHistory.course_id == course_id)
            .order_by(ConversationHistory.created_at.desc())
            .limit(limit)
        )
        rows = list(self.session.exec(statement))
        return list(reversed(rows))

    def get_page(
        self,
        *,
        course_id: int | None = None,
        module_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ConversationHistory], int]:
        """Paginated, newest-first history for GET /agent/history."""
        base = select(ConversationHistory).where(
            ConversationHistory.learner_id == self.learner_id
        )
        if course_id is not None:
            base = base.where(ConversationHistory.course_id == course_id)
        if module_id is not None:
            base = base.where(ConversationHistory.module_id == module_id)

        total = self.session.exec(
            select(func.count()).select_from(base.subquery())
        ).one()

        rows = self.session.exec(
            base.order_by(ConversationHistory.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), total


class QueryLogRepository:
    """Write-side access to `query_logs`. No RBAC scoping needed here — it's
    written internally by the agent service, never taken from a request."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        learner_id: int,
        course_id: int,
        module_id: int | None,
        assignment_id: int | None,
        query_type: str,
        question: str,
        top_retrieval_score: float | None,
        confidence_score: float,
        is_confident: bool,
        escalated: bool,
        escalation_reason: str | None,
        escalation_detail: str | None,
        escalation_id: int | None,
    ) -> QueryLog:
        log = QueryLog(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
            assignment_id=assignment_id,
            query_type=query_type,
            question=question,
            top_retrieval_score=top_retrieval_score,
            confidence_score=confidence_score,
            is_confident=is_confident,
            escalated=escalated,
            escalation_reason=escalation_reason,
            escalation_detail=escalation_detail,
            escalation_id=escalation_id,
        )
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log
