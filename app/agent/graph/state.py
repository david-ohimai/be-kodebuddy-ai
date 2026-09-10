"""
LangGraph state schema for the KodeBuddy AI learning assistant agent.

This defines the single shared state object that flows through the graph:
retrieve -> (reason -> confidence_gate) | no_context -> route.

Owner: Dev C (Graph / Reasoning / Guardrails)
"""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


class QueryType(str, Enum):
    CHAT = "chat"
    ASSIGNMENT_GUIDANCE = "assignment_guidance"


class EscalationReason(str, Enum):
    NO_RELEVANT_CONTEXT = "no_relevant_context"
    LOW_RETRIEVAL_CONFIDENCE = "low_retrieval_confidence"
    MODEL_UNCERTAINTY = "model_uncertainty"
    POLICY_VIOLATION = "policy_violation"
    PARSER_FAILURE = "parser_failure"
    RETRIEVAL_UNAVAILABLE = "retrieval_unavailable"
    EXPLICIT_USER_REQUEST = "explicit_user_request"
    OTHER = "other"


class RetrievedChunk(TypedDict):
    chunk_id: str
    course_id: int | None
    module_id: int | None
    content_type: str
    text: str
    score: float


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatTurn(TypedDict, total=False):
    role: str
    message: str
    retrieved_assignment_content: bool


class AssignmentBrief(TypedDict):
    assignment_id: int
    course_id: int
    module_id: int
    title: str
    description: str
    due_date: str | None
    maximum_score: int | None


class AgentState(TypedDict, total=False):
    learner_id: int
    course_id: int
    module_id: int | None
    assignment_id: int | None
    trainer_id: int | None
    question: str
    query_type: QueryType
    chat_history: list[ChatTurn]

    retrieved_chunks: list[RetrievedChunk]
    assignment_brief: AssignmentBrief | None
    retrieval_failed: bool

    draft_response: str
    model_expressed_uncertainty: bool

    policy_violation: bool
    parser_failed: bool

    confidence_score: float
    is_confident: bool
    escalation_reason: EscalationReason | None
    escalation_detail: str | None

    final_response: str | None
    escalated: bool
    escalation_id: int | None
    escalation_available: bool