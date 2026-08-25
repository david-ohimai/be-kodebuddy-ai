"""
Tool: search_curriculum — scoped similarity search over module content.

Owner: Dev B (Retrieval & Tools)

Matches Dev C's `SearchCurriculumFn` protocol. The learner is bound when the
tool is built rather than passed per call, so RBAC scoping cannot be omitted or
spoofed by the caller; see `app.agent.repository` for the enforcing join.
"""

from __future__ import annotations

import logging
from typing import Callable

from app.agent.embedding_seam import embed_query
from app.agent.repository import DEFAULT_SEARCH_LIMIT, AgentRepository
from app.agent.types import CURRICULUM, RetrievedChunk

logger = logging.getLogger(__name__)

SearchCurriculum = Callable[..., "list[RetrievedChunk]"]


def make_search_curriculum(
    repository: AgentRepository,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,
    min_score: float | None = None,
) -> SearchCurriculum:
    """Build a `search_curriculum` bound to one learner's repository."""

    def search_curriculum(
        *,
        query: str,
        course_id: int,
        module_id: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Search curriculum content the learner is entitled to see.

        Args:
            query: the learner's question, in natural language.
            course_id: course to search within.
            module_id: optional module to narrow to.

        Returns:
            Chunks ordered most-similar first. Empty when nothing relevant is
            found *or* when the learner is not enrolled in `course_id` — the
            two are intentionally indistinguishable to the caller.

        Raises:
            EmbeddingUnavailableError: the query could not be embedded.
            ContentStoreUnavailableError: the embeddings table is missing.

            Both are raised rather than returned as an empty list, because a
            caller cannot otherwise tell "searched, found nothing" from "never
            actually searched" — and the second must not be answered as if it
            were the first.
        """
        if not query or not query.strip():
            logger.debug("search_curriculum called with a blank query.")
            return []

        embedding = embed_query(query)
        return repository.search_content(
            query_embedding=embedding,
            course_id=course_id,
            module_id=module_id,
            content_type=CURRICULUM,
            limit=limit,
            min_score=min_score,
        )

    return search_curriculum
