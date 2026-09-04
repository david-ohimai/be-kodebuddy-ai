"""
Errors and content-type vocabulary for the retrieval tools.

Owner: Dev B (Retrieval & Tools)

The shared data shapes — `RetrievedChunk`, `AssignmentBrief`,
`EscalationReason` — are NOT defined here. They live in
`app.agent.graph.state`, owned by Dev C, and are re-exported below so callers
of this package have one import site.

This file used to carry its own structural copies of those types, from before
the graph existed on `dev`. That is now a liability rather than a convenience:
two definitions of the same shape drift silently (the `due_date` type already
diverged once — `date` here, ISO-8601 `str` there). `state.py` imports nothing
from this package, so depending on it introduces no cycle.
"""

from __future__ import annotations

from typing import Literal

from app.agent.graph.state import (
    AssignmentBrief,
    EscalationReason,
    RetrievedChunk,
)

# Values stored in `content_embeddings.content_type` (Dev A's table).
ContentType = Literal["curriculum", "faq", "resource"]

CURRICULUM: ContentType = "curriculum"
FAQ: ContentType = "faq"
RESOURCE: ContentType = "resource"


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


class AgentRetrievalError(RuntimeError):
    """Base class for every failure raised by the retrieval layer."""


class EmbeddingUnavailableError(AgentRetrievalError):
    """
    Dev A's embedding provider is missing, misconfigured, or failed.

    Raised rather than returning `[]` because an empty result is
    indistinguishable from "no relevant content", which would cause the
    confidence gate to escalate a question that was never actually searched.
    """


class ContentStoreUnavailableError(AgentRetrievalError):
    """
    The `content_embeddings` table (or the pgvector extension) is not present.

    Expected until Dev A's migration has been applied. Distinct from "no
    results" for the same reason as `EmbeddingUnavailableError`.
    """


class EscalationWriteError(AgentRetrievalError):
    """The escalation record could not be persisted."""


__all__ = [
    "AgentRetrievalError",
    "AssignmentBrief",
    "CURRICULUM",
    "ContentStoreUnavailableError",
    "ContentType",
    "EmbeddingUnavailableError",
    "EscalationReason",
    "EscalationWriteError",
    "FAQ",
    "RESOURCE",
    "RetrievedChunk",
]
