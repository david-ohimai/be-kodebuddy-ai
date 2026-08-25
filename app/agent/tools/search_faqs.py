"""
Tool: search_faqs — same index as curriculum search, filtered to FAQ content.

Owner: Dev B (Retrieval & Tools)

`course_id` is REQUIRED, matching `SearchFaqsFn` in graph/contracts.py.

An earlier revision made it optional, to hedge against the still-open question
of whether KodeCamp's FAQs are per-course or general. That hedge is withdrawn:
an implementation that disagrees with its own published contract is worse than
one that is provisionally too narrow. The graph passes `course_id` on every
call today (nodes.py::retrieve), so nothing is lost by requiring it.

If the FAQs turn out to be general rather than per-course, widening this back
to `int | None` is a backward-compatible change — adding a default breaks no
existing caller — and the repository already supports it (`search_content`
treats `course_id=None` as "every course this learner is enrolled in").
Whichever way it lands, access does not widen: the underlying query joins
`course_learners` regardless, so an unscoped FAQ search would still cover the
learner's own courses and nothing else.
"""

from __future__ import annotations

import logging
from typing import Callable

from app.agent.embedding_seam import embed_query
from app.agent.repository import DEFAULT_SEARCH_LIMIT, AgentRepository
from app.agent.types import FAQ, RetrievedChunk

logger = logging.getLogger(__name__)

SearchFaqs = Callable[..., "list[RetrievedChunk]"]


def make_search_faqs(
    repository: AgentRepository,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,
    min_score: float | None = None,
) -> SearchFaqs:
    """Build a `search_faqs` bound to one learner's repository."""

    def search_faqs(
        *,
        query: str,
        course_id: int,
    ) -> list[RetrievedChunk]:
        """
        Search FAQ content the learner is entitled to see.

        Args:
            query: the learner's question, in natural language.
            course_id: course to search within. Required, per SearchFaqsFn.

        Returns:
            Chunks ordered most-similar first; empty when nothing matches.

        Raises:
            EmbeddingUnavailableError: the query could not be embedded.
            ContentStoreUnavailableError: the embeddings table is missing.
        """
        if not query or not query.strip():
            logger.debug("search_faqs called with a blank query.")
            return []

        embedding = embed_query(query)
        return repository.search_content(
            query_embedding=embedding,
            course_id=course_id,
            content_type=FAQ,
            limit=limit,
            min_score=min_score,
        )

    return search_faqs
