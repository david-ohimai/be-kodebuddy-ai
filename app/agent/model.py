from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import SQLModel, Field, Column, JSON
from pgvector.sqlalchemy import Vector
from app.agent.graph.state import EscalationReason

# Resolve circular dependency and ensure SQLAlchemy knows about related tables
from app.features.auth.model import User  # noqa: F401
from app.features.courses.model import Course  # noqa: F401
from app.features.modules.model import Module  # noqa: F401


class ContentEmbedding(SQLModel, table=True):
    __tablename__ = "content_embeddings"

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    module_id: Optional[int] = Field(
        default=None,
        foreign_key="modules.id",
        index=True,
        nullable=True,
    )
    content_type: str = Field(max_length=50, index=True)  # "curriculum" | "faq" | "resource"
    text: str = Field(nullable=False)
    embedding: List[float] = Field(sa_column=Column(Vector(1024), nullable=False))


class Escalation(SQLModel, table=True):
    __tablename__ = "escalations"

    id: Optional[int] = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    trainer_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,
    )
    question: str = Field(nullable=False)
    reason: EscalationReason = Field(nullable=False)
    detail: Optional[str] = Field(default=None, nullable=True)
    status: str = Field(default="pending", max_length=50, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ConversationHistory(SQLModel, table=True):
    __tablename__ = "conversation_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    role: str = Field(max_length=50, index=True)  # "user" | "assistant"
    message: str = Field(nullable=False)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class QueryLog(SQLModel, table=True):
    __tablename__ = "query_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    question: str = Field(nullable=False)
    retrieved_chunk_ids: List[str] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    confidence_score: float = Field(nullable=False)
    escalated: bool = Field(default=False, index=True)
    latency_ms: int = Field(nullable=False)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
