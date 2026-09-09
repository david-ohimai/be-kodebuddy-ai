from datetime import datetime, timezone
from typing import List, Optional
from sqlmodel import SQLModel, Field, Column, JSON
from pgvector.sqlalchemy import Vector
from app.agent.graph.state import ChatRole, EscalationReason
from sqlalchemy import Enum as SAEnum
from app.features.auth.model import User  
from app.features.courses.model import Course 
from app.features.modules.model import Module  
from app.features.assignments.model import Assignment 


class ContentEmbedding(SQLModel, table=True):
    __tablename__ = "content_embeddings"

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: Optional[int] = Field(
        default=None,
        foreign_key="courses.id",
        index=True,
        nullable=True,
    )
    module_id: Optional[int] = Field(
        default=None,
        foreign_key="modules.id",
        index=True,
        nullable=True,
    )
    content_type: str = Field(max_length=50, index=True) 
    source_type: str = Field(max_length=50)  
    source_id: int                           
    chunk_index: int = Field(default=0)       
    content_hash: Optional[str] = Field(default=None, max_length=64)
    embedding_model: Optional[str] = Field(default=None, max_length=100) 
    text: str = Field(nullable=False)
    embedding: List[float] = Field(sa_column=Column(Vector(1024), nullable=False))
    
class Escalation(SQLModel, table=True):
    __tablename__ = "escalations"

    id: Optional[int] = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    module_id: Optional[int] = Field(
        default=None,
        foreign_key="modules.id",
        index=True,
        nullable=True,
    )
    assignment_id: Optional[int] = Field(
        default=None,
        foreign_key="assignments.id",
        index=True,
        nullable=True,
    )
    trainer_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
        nullable=True,
    )
    question: str = Field(nullable=False)
    reason: EscalationReason = Field(
        sa_column=Column(
            SAEnum(
                EscalationReason,
                name="escalationreason",
                values_callable=lambda enum_cls: [member.value for member in enum_cls],
            ),
            nullable=False,
        )
    )
    detail: Optional[str] = Field(default=None, nullable=True)
    draft_response: Optional[str] = Field(default=None, nullable=True)
    confidence_score: Optional[float] = Field(default=None, nullable=True)
    response: Optional[str] = Field(default=None, nullable=True)
    responded_at: Optional[datetime] = Field(default=None, nullable=True)
    status: str = Field(default="open", max_length=50, index=True)
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
    module_id: Optional[int] = Field(
        default=None,
        foreign_key="modules.id",
        index=True,
        nullable=True,
    )
    role: ChatRole = Field(
        sa_column=Column(
            SAEnum(
                ChatRole,
                name="chatrole",
                values_callable=lambda enum_cls: [member.value for member in enum_cls],
            ),
            nullable=False,
        )
    )
    message: str = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )


class QueryLog(SQLModel, table=True):
    """
    One record per graph run, capturing the confidence/escalation metrics
    needed for observability and analytics.

    Superset of the design doc's originally-specified columns (question,
    retrieved_chunk_ids, confidence_score, escalated, latency_ms) and Dev
    E's richer observability columns (query_type, is_confident,
    escalation_reason/detail/id, top_retrieval_score) reconciled into one
    table — see the model-schema discussion that replaced the duplicate
    app/features/agent/model.py definition of this same table name.
    """

    __tablename__ = "query_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    learner_id: int = Field(foreign_key="users.id", index=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    module_id: Optional[int] = Field(
        default=None,
        foreign_key="modules.id",
        index=True,
        nullable=True,
    )
    assignment_id: Optional[int] = Field(
        default=None,
        foreign_key="assignments.id",
        index=True,
        nullable=True,
    )
    query_type: str = Field(max_length=50, index=True)  
    question: str = Field(nullable=False)
    retrieved_chunk_ids: List[str] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    top_retrieval_score: Optional[float] = Field(default=None, nullable=True)
    confidence_score: float = Field(nullable=False)
    is_confident: bool = Field(nullable=False, index=True)
    escalated: bool = Field(default=False, index=True)
    escalation_reason: Optional[str] = Field(
        default=None,
        max_length=50,
        index=True,
        nullable=True,
    )
    escalation_detail: Optional[str] = Field(default=None, nullable=True)
    escalation_id: Optional[int] = Field(
        default=None,
        foreign_key="escalations.id",
        nullable=True,
    )
    latency_ms: int = Field(nullable=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )