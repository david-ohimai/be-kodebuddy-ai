"""
Explicit interface contracts between Dev C's graph and the modules owned by
Dev B (retrieval tools) and Dev D (LLM client / service wiring).

Nothing in this file has real logic. It exists so that:

  1. Dev C can build and unit-test the graph against fakes that satisfy these
     Protocols, without waiting on Dev B's tools or Dev D's LLM client to
     exist yet.
  2. Dev B and Dev D have a pinned, reviewable signature to implement
     against, instead of reverse-engineering one from nodes.py.

If a signature here needs to change, that's a conversation with the owning
dev (raise it in standup / the thread), not a silent edit in nodes.py.

Mapping to the PRD's documented tool list:
    search_curriculum(query, course_id, module_id?)   -> SearchCurriculumFn
    search_faqs(query, course_id)                      -> SearchFaqsFn
    get_assignment_brief(assignment_id)                 -> GetAssignmentBriefFn
    escalate_to_trainer(learner_id, course_id, question, reason)
    -> EscalateToTrainerFn
"""

from __future__ import annotations

from typing import Protocol

from app.agent.graph.state import RetrievedChunk


class SearchCurriculumFn(Protocol):
    """Dev B: scoped similarity search over module content."""

    def __call__(
        self, *, query: str, course_id: str, module_id: str | None = None
    ) -> list[RetrievedChunk]: ...


class SearchFaqsFn(Protocol):
    """Dev B: same index as curriculum search, filtered to FAQ content type."""

    def __call__(self, *, query: str, course_id: str
                 ) -> list[RetrievedChunk]: ...


class GetAssignmentBriefFn(Protocol):
    """Dev B: structured lookup (not free-text search)
    of an assignment brief."""

    def __call__(self, assignment_id: str) -> str | None: ...


class EscalateToTrainerFn(Protocol):
    """
    Dev B: writes an escalation record for the trainer dashboard to read.
    Returns the new escalation's id, which the graph surfaces back to the
    caller (and, eventually, the learner-facing UI).
    """

    def __call__(
        self, *, learner_id: str, course_id: str, question: str, reason: str
    ) -> str: ...


class LLMClient(Protocol):
    """
    Dev D: thin wrapper around whatever LLM provider is chosen. The graph
    only ever needs a system prompt + user turn in, completion text out —
    keeping this abstract means swapping providers or adding
    retries/timeouts in the real client never touches node logic.
    """

    def complete(self, *, system: str, user: str) -> str: ...
