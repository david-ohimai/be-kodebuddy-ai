from __future__ import annotations

import logging
from typing import Callable

from app.agent.embedding_seam import embed_query
from app.agent.repository import DEFAULT_SEARCH_LIMIT, AgentRepository
from app.agent.types import ASSIGNMENT, RetrievedChunk

logger = logging.getLogger(__name__)

SearchAssignments = Callable[..., "list[RetrievedChunk]"]


def make_search_assignments(
    repository: AgentRepository,
    *,
    limit: int = DEFAULT_SEARCH_LIMIT,
    min_score: float | None = None,
) -> SearchAssignments:

    def search_assignments(
        *,
        query: str,
        course_id: int,
        module_id: int | None = None,
    ) -> list[RetrievedChunk]:
        if not query or not query.strip():
            logger.debug("search_assignments called with a blank query.")
            return []

        embedding = embed_query(query)
        return repository.search_content(
            query_embedding=embedding,
            course_id=course_id,
            module_id=module_id,
            content_type=ASSIGNMENT,
            limit=limit,
            min_score=min_score,
        )

    return search_assignments