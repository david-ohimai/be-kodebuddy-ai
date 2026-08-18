"""
LangGraph state schema for the KodeBuddy AI learning assistant agent.

This defines the single shared state object that flows through all four
graph nodes: retrieve -> reason -> confidence_gate -> route.

Owner: Dev C (Graph / Reasoning / Guardrails)
"""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


class QueryType(str, Enum):
    """Distinguishes a general curriculum question from assignment guidance."""

    CHAT = "chat"
    ASSIGNMENT_GUIDANCE = "assignment_guidance"


class RetrievedChunk(TypedDict):
    """One retrieved piece of grounding content,
    as returned by Dev B's tools."""

    chunk_id: str
    course_id: str
    module_id: str | None
    content_type: str  # "curriculum" | "faq" | "resource"
    text: str
    score: float


class ChatTurn(TypedDict):
    """One turn of prior conversation, as loaded from conversation_history."""

    role: str  # "user" | "assistant"
    message: str


class AgentState(TypedDict, total=False):
    """
    Shared state object passed between graph nodes.

    Fields are grouped by which node reads/writes them:
      - input fields:    set once by Dev D's service.py before graph.invoke()
      - retrieve fields:  written by `retrieve`, read by `reason`
      - reason fields:    written by `reason`, read by `confidence_gate`
      - gate fields:      written by `confidence_gate`, read by `route`
      - output fields:    written by `route`, read by Dev D's service.py

    NOTE for integrators: this TypedDict is intentionally `total=False` because
    each node only fills in *its* fields — LangGraph merges partial updates
    into the running state, it doesn't require every key up front.
    """

    # --- input (set by Dev D's service.py before invoking the graph) ---
    learner_id: str
    course_id: str
    module_id: str | None
    assignment_id: str | None
    question: str
    query_type: QueryType
    # windowed recent history, loaded by Dev E's history logic
    chat_history: list[ChatTurn]

    # --- retrieve node output ---
    retrieved_chunks: list[RetrievedChunk]
    assignment_brief: str | None  # only populated for ASSIGNMENT_GUIDANCE

    # --- reason node output ---
    draft_response: str
    model_expressed_uncertainty: bool

    # --- confidence_gate node output ---
    confidence_score: float
    is_confident: bool
    escalation_reason: str | None

    # --- route node output (final) ---
    final_response: str | None
    escalated: bool
    escalation_id: str | None
