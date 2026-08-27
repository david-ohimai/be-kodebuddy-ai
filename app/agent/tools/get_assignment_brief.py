"""
Tool: get_assignment_brief — structured lookup of one assignment.

Owner: Dev B (Retrieval & Tools)

This is a direct lookup, not a similarity search: the graph already knows which
assignment the learner is asking about, so guessing at it via embeddings would
only add a way to be wrong.

Returns the structured `AssignmentBrief`, not a pre-formatted string. That
changed when Dev C's graph merged: rendering the brief into prompt text is a
prompt-design decision and now lives in `prompts/assignment_guidance.py`
(`_format_assignment_brief`). This module deliberately no longer formats
anything, so there is exactly one place that decides how a due date or a
maximum score gets phrased to the model.
"""

from __future__ import annotations

import logging
from typing import Callable

from app.agent.repository import AgentRepository
from app.agent.types import AssignmentBrief

logger = logging.getLogger(__name__)

GetAssignmentBrief = Callable[[int], "AssignmentBrief | None"]


def make_get_assignment_brief(
    repository: AgentRepository,
) -> GetAssignmentBrief:
    """Build a `get_assignment_brief` bound to one learner's repository."""

    def get_assignment_brief(assignment_id: int) -> AssignmentBrief | None:
        """
        Look up an assignment brief the learner is entitled to see.

        Args:
            assignment_id: the assignment to fetch.

        Returns:
            The structured brief, or None when the assignment does not exist,
            is inactive, or the learner is not enrolled in its course. Those
            cases are not distinguished, so this cannot be used to probe which
            assignment ids exist.
        """
        if assignment_id is None:
            return None

        try:
            normalised_id = int(assignment_id)
        except (TypeError, ValueError):
            logger.warning(
                "get_assignment_brief called with a non-numeric id: %r",
                assignment_id,
            )
            return None

        return repository.get_assignment(normalised_id)

    return get_assignment_brief
