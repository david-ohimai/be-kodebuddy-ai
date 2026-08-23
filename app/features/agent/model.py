from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class ChatRole(str, Enum):
    """Mirrors ChatTurn["role"] in app/agent/graph/state.py."""

    USER = "user"
    ASSISTANT = "assistant"


class ConversationHistory(SQLModel, table=True):
    """
    One turn of a learner<->agent conversation.

    Written twice per graph run — once for the learner's question, once for
    the agent's final_response — and read back windowed (most recent N turns
    for a learner/course/module) to populate AgentState.chat_history before
    the next graph.invoke().

    module_id is nullable because a CHAT-type question isn't necessarily
    scoped to a single module, matching AgentState.module_id.
    """

    __tablename__ = "conversation_history"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    learner_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    course_id: int = Field(
        foreign_key="courses.id",
        index=True,
    )

    module_id: int | None = Field(
        default=None,
        foreign_key="modules.id",
        index=True,
    )

    role: ChatRole

    message: str

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )


class QueryLog(SQLModel, table=True):
    """
    One record per graph run, capturing the confidence/escalation metrics
    needed for observability and analytics — every field here is read
    straight off the final AgentState (see app/agent/graph/state.py), so a
    row can be reconstructed without re-running the graph.

    query_type/escalation_reason are stored as plain strings (not FKs to the
    enums) so this table has no import-time dependency on app/agent/graph —
    the enum values are stable strings, and query_logs should be readable
    even if the graph module is refactored later.
    """

    __tablename__ = "query_logs"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    learner_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    course_id: int = Field(
        foreign_key="courses.id",
        index=True,
    )

    module_id: int | None = Field(
        default=None,
        foreign_key="modules.id",
    )

    assignment_id: int | None = Field(
        default=None,
        foreign_key="assignments.id",
    )

    query_type: str = Field(index=True)

    question: str

    top_retrieval_score: float | None = None

    confidence_score: float

    is_confident: bool = Field(index=True)

    escalated: bool = Field(index=True)

    escalation_reason: str | None = Field(
        default=None,
        index=True,
    )

    escalation_detail: str | None = None

    # No FK constraint: the `escalations` table belongs to Dev A/B's work,
    # which hasn't landed on this branch yet. Once it has, a migration can
    # add the constraint without touching this model.
    escalation_id: int | None = Field(default=None)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
