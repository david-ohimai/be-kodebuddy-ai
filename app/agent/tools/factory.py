"""
Per-request construction of the agent's tools.

Owner: Dev B (Retrieval & Tools)

WHY A FACTORY RATHER THAN PLAIN FUNCTIONS
-----------------------------------------
Dev C's tool protocols do not include `learner_id` — `search_curriculum` takes
only `(query, course_id, module_id?)`. But every retrieval must be scoped to
the learner, or the RBAC guarantee is not a guarantee.

Binding the learner (and the DB session) at construction resolves that without
changing a single documented signature: the graph keeps calling the tools
exactly as specified, and there is no argument a node could forget to pass or
pass wrongly. Build one `AgentTools` per request, in Dev D's service layer,
from the authenticated user.

`as_mapping()` returns exactly the four tool keyword arguments that Dev C's
`AgentDependencies` expects, so wiring is a single splat:

    from app.agent.graph.build import build_agent_graph
    from app.agent.graph.nodes import AgentDependencies

    tools = AgentTools.for_learner(session, current_user.id)
    deps = AgentDependencies(llm=llm_client, **tools.as_mapping())
    graph = build_agent_graph(deps)

Build the graph per request too, or cache it per learner — never share one
graph across learners, since the tools inside it carry a learner id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from app.agent.repository import DEFAULT_SEARCH_LIMIT, AgentRepository
from app.agent.tools.escalate_to_trainer import make_escalate_to_trainer
from app.agent.tools.get_assignment_brief import make_get_assignment_brief
from app.agent.tools.search_curriculum import make_search_curriculum
from app.agent.tools.search_faqs import make_search_faqs


@dataclass(frozen=True)
class AgentTools:
    """
    The agent's four tools, all scoped to one learner.

    Attribute names match the tool names in the design document, so the
    mapping to Dev C's protocols is one-to-one.
    """

    repository: AgentRepository
    search_curriculum: Any
    search_faqs: Any
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
        """
        Build the tool set for one learner.

        Args:
            session: an open DB session (FastAPI's `get_session` dependency).
            learner_id: the *authenticated* user's id. Never take this from
                the request body — it is the entire access control boundary.
            limit: default chunks per search.
            min_score: optional similarity floor applied to both searches.
        """
        repository = AgentRepository(session=session, learner_id=learner_id)
        return cls(
            repository=repository,
            search_curriculum=make_search_curriculum(
                repository, limit=limit, min_score=min_score
            ),
            search_faqs=make_search_faqs(
                repository, limit=limit, min_score=min_score
            ),
            get_assignment_brief=make_get_assignment_brief(repository),
            escalate_to_trainer=make_escalate_to_trainer(repository),
        )

    @property
    def learner_id(self) -> int:
        """The learner every tool in this set is scoped to."""
        return self.repository.learner_id

    def as_mapping(self) -> dict[str, Any]:
        """The four tools keyed by name, for injection into the graph."""
        return {
            "search_curriculum": self.search_curriculum,
            "search_faqs": self.search_faqs,
            "get_assignment_brief": self.get_assignment_brief,
            "escalate_to_trainer": self.escalate_to_trainer,
        }
