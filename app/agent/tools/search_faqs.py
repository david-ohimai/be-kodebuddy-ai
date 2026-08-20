"""
Tool: search_faqs — same index as curriculum search, filtered to FAQ content.

Owner: Dev B (Retrieval & Tools)

`course_id` is OPTIONAL here, which is a deliberate widening of Dev C's
original `SearchFaqsFn` protocol. At the time of writing it is still undecided
whether KodeCamp's FAQs are per-course or general (they are being supplied as a
JSON file for ingestion rather than modelled as a table). An optional filter
serves both outcomes without blocking Dev C or Dev D on that answer:

  * per-course FAQs  -> pass course_id, behaves as originally specified
  * general FAQs     -> omit it, searches every course the learner is in

Note that omitting `course_id` still does not widen *access*: the underlying
query joins `course_learners` either way, so an unscoped FAQ search covers the
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
        course_id: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Search FAQ content the learner is entitled to see.

        Args:
            query: the learner's question, in natural language.
            course_id: optional course filter. When omitted, searches FAQs
                across every course the learner is enrolled in.

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
