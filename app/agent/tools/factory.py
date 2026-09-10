from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from app.agent.repository import DEFAULT_SEARCH_LIMIT, AgentRepository
from app.agent.tools.escalate_to_trainer import make_escalate_to_trainer
from app.agent.tools.get_assignment_brief import make_get_assignment_brief
from app.agent.tools.search_assignments import make_search_assignments
from app.agent.tools.search_curriculum import make_search_curriculum
from app.agent.tools.search_faqs import make_search_faqs


@dataclass(frozen=True)
class AgentTools:
    repository: AgentRepository
    search_curriculum: Any
    search_faqs: Any
    search_assignments: Any
    get_assignment_brief: Any
    escalate_to_trainer: Any

    @classmethod
    def for_learner(
        cls,
        session: Session,
        learner_id: int,
        *,
        limit: int = DEFAULT_SEARCH_LIMIT,
        min_score: float | None = None,
    ) -> "AgentTools":
        repository = AgentRepository(session=session, learner_id=learner_id)
        return cls(
            repository=repository,
            search_curriculum=make_search_curriculum(
                repository, limit=limit, min_score=min_score
            ),
            search_faqs=make_search_faqs(
                repository, limit=limit, min_score=min_score
            ),
            search_assignments=make_search_assignments(
                repository, limit=limit, min_score=min_score
            ),
            get_assignment_brief=make_get_assignment_brief(repository),
            escalate_to_trainer=make_escalate_to_trainer(repository),
        )

    @property
    def learner_id(self) -> int:
        return self.repository.learner_id

    def as_mapping(self) -> dict[str, Any]:
        return {
            "search_curriculum": self.search_curriculum,
            "search_faqs": self.search_faqs,
            "search_assignments": self.search_assignments,
            "get_assignment_brief": self.get_assignment_brief,
            "escalate_to_trainer": self.escalate_to_trainer,
        }