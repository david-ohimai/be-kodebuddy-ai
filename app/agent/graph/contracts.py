from __future__ import annotations

from typing import Protocol

from app.agent.graph.state import (
    AssignmentBrief,
    EscalationReason,
    RetrievedChunk,
)


class SearchCurriculumFn(Protocol):
    def __call__(
        self, *, query: str, course_id: int, module_id: int | None = None
    ) -> list[RetrievedChunk]: ...


class SearchFaqsFn(Protocol):
    def __call__(
        self, *, query: str, course_id: int
    ) -> list[RetrievedChunk]: ...


class SearchAssignmentsFn(Protocol):
    def __call__(
        self, *, query: str, course_id: int, module_id: int | None = None
    ) -> list[RetrievedChunk]: ...


class GetAssignmentBriefFn(Protocol):
    def __call__(self, assignment_id: int) -> AssignmentBrief | None: ...


class EscalateToTrainerFn(Protocol):
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
    def complete(self, *, system: str, user: str) -> str: ...