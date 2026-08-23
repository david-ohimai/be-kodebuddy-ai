"""
Service layer bridging `conversation_history` / `query_logs` to the agent
graph's `AgentState` (app/agent/graph/state.py).

Owner: Dev E (History, Observability & Evals)

Intended usage by Dev D's service.py, around a single graph.invoke() call:

    history_repo = ConversationHistoryRepository(session, learner_id)
    chat_history = load_chat_history(
        history_repo, course_id=course_id, module_id=module_id,
        max_turns=deps.max_history_turns,
    )
    initial_state = {..., "chat_history": chat_history}
    result_state = graph.invoke(initial_state)
    record_interaction(session, learner_id=learner_id, state=result_state)
"""

from __future__ import annotations

from sqlmodel import Session

from app.agent.graph.state import AgentState, ChatTurn, QueryType
from app.agent.graph.utils import chunk_score

from .model import ChatRole
from .repository import ConversationHistoryRepository, QueryLogRepository


def load_chat_history(
    history_repo: ConversationHistoryRepository,
    *,
    course_id: int,
    module_id: int | None,
    max_turns: int,
) -> list[ChatTurn]:
    """Loads the most recent turns as the `ChatTurn` shape AgentState
    expects, ready to drop straight into `chat_history`."""
    rows = history_repo.get_recent(
        course_id=course_id, module_id=module_id, limit=max_turns
    )
    return [ChatTurn(role=row.role.value, message=row.message) for row in rows]


def record_interaction(
    session: Session,
    *,
    learner_id: int,
    course_id: int,
    module_id: int | None,
    state: AgentState,
) -> None:
    """
    Persists both sides of one turn's history and the query_log row for that
    same run. Called once per graph.invoke(), after routing.

    Deliberately takes the *final* AgentState rather than individual
    keyword args — this is the one place that should know AgentState's
    shape, so Dev D's caller doesn't need to unpack it field by field.
    """
    history_repo = ConversationHistoryRepository(session, learner_id)
    history_repo.add_exchange(
        course_id=course_id,
        module_id=module_id,
        question=state["question"],
        final_response=state.get("final_response") or "",
    )

    chunks = state.get("retrieved_chunks") or []
    top_score = max((chunk_score(c) for c in chunks), default=None)

    query_type = state.get("query_type")
    escalation_reason = state.get("escalation_reason")

    QueryLogRepository(session).record(
        learner_id=learner_id,
        course_id=course_id,
        module_id=module_id,
        assignment_id=state.get("assignment_id"),
        query_type=(
            query_type.value if isinstance(query_type, QueryType) else query_type
        )
        or QueryType.CHAT.value,
        question=state["question"],
        top_retrieval_score=top_score,
        confidence_score=state.get("confidence_score", 0.0),
        is_confident=bool(state.get("is_confident", False)),
        escalated=bool(state.get("escalated", False)),
        escalation_reason=(
            escalation_reason.value
            if hasattr(escalation_reason, "value")
            else escalation_reason
        ),
        escalation_detail=state.get("escalation_detail"),
        escalation_id=state.get("escalation_id"),
    )


__all__ = ["load_chat_history", "record_interaction", "ChatRole"]
