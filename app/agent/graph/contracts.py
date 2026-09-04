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

Entity ids are `int` throughout, matching the backend's primary keys
(users/courses/modules/assignments/escalations are all int PKs). Only
`chunk_id` on RetrievedChunk stays `str` — see state.py for why.
"""

from __future__ import annotations

from typing import Protocol

from app.agent.graph.state import (
    AssignmentBrief,
    EscalationReason,
    RetrievedChunk,
)


class SearchCurriculumFn(Protocol):
    """Dev B: scoped similarity search over module content."""

    def __call__(
        self, *, query: str, course_id: int, module_id: int | None = None
    ) -> list[RetrievedChunk]: ...


class SearchFaqsFn(Protocol):
    """Dev B: same index as curriculum search, filtered to FAQ content type."""

    def __call__(
        self, *, query: str, course_id: int
        ) -> list[RetrievedChunk]: ...


class GetAssignmentBriefFn(Protocol):
    """
    Dev B: structured lookup (not free-text search) of an assignment brief.

    Returns the structured AssignmentBrief (title/description/due_date/
    maximum_score), not a pre-formatted string — how those fields get
    phrased into the prompt is decided in prompts/assignment_guidance.py,
    owned by Dev C.
    """

    def __call__(self, assignment_id: int) -> AssignmentBrief | None: ...


class EscalateToTrainerFn(Protocol):
    """
    Dev B: writes an escalation record for the trainer dashboard to read.
    Returns the new escalation row's int id, which the graph surfaces back
    to the caller (and, eventually, the learner-facing UI).

    `trainer_id` is a `users.id` value - the backend has one unified
    `users` table (no separate `trainers` table/module), so "the trainer"
    for a course/cohort is just a user whose role happens to be trainer.
    The graph doesn't resolve this itself; it's looked up upstream by Dev D
    and passed through AgentState. It's Optional here because the graph
    must still be able to escalate rather than silently drop the question
    even if that lookup failed; Dev B's implementation decides the fallback
    (e.g. an unassigned-escalations queue) when it's None.

    `reason` is the structured EscalationReason enum, not a free-form
    string, so escalation metrics can be aggregated by category. `detail`
    carries any free-form context (e.g. the actual retrieval score) that
    doesn't belong in the category itself.
    """

    def __call__(
        self,
        *,
        learner_id: int,
        course_id: int,
        trainer_id: int | None,
        question: str,
        reason: EscalationReason,
        detail: str | None = None,
    ) -> int: ...


class LLMClient(Protocol):
    """
    Dev D: thin wrapper around whatever LLM provider is chosen. The graph
    only ever needs a system prompt + user turn in, completion text out —
    keeping this abstract means swapping providers or adding
    retries/timeouts in the real client never touches node logic.
    """

    def complete(self, *, system: str, user: str) -> str: ...
