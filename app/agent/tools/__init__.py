"""
Agent tools (Dev B — Retrieval & Tools).

Public surface for Dev C's graph and Dev D's service layer. Import the factory
rather than the individual `make_*` builders unless you have a reason not to::

    from app.agent.tools import AgentTools

    tools = AgentTools.for_learner(session, learner_id)
    chunks = tools.search_curriculum(query="...", course_id=1)
"""

from app.agent.tools.escalate_to_trainer import make_escalate_to_trainer
from app.agent.tools.factory import AgentTools
from app.agent.tools.get_assignment_brief import make_get_assignment_brief
from app.agent.tools.search_curriculum import make_search_curriculum
from app.agent.tools.search_faqs import make_search_faqs
from app.agent.types import (
    AgentRetrievalError,
    AssignmentBrief,
    ContentStoreUnavailableError,
    ContentType,
    EmbeddingUnavailableError,
    EscalationReason,
    EscalationWriteError,
    RetrievedChunk,
)

__all__ = [
    "AgentTools",
    "AgentRetrievalError",
    "AssignmentBrief",
    "ContentStoreUnavailableError",
    "ContentType",
    "EmbeddingUnavailableError",
    "EscalationReason",
    "EscalationWriteError",
    "RetrievedChunk",
    "make_escalate_to_trainer",
    "make_get_assignment_brief",
    "make_search_curriculum",
    "make_search_faqs",
]
