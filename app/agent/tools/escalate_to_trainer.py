"""
Tool: escalate_to_trainer — record a question the agent could not answer.

Owner: Dev B (Retrieval & Tools), provisionally.

OWNERSHIP NOTE: the task split lists three tools against Dev B
(search_curriculum, search_faqs, get_assignment_brief) but also assigns
"escalation writes" to Dev B's repository.py, and Dev C's contracts.py lists
this tool as Dev B's. It is implemented here on that basis. Raised with the
team rather than assumed silently — if it should move, only this file and the
factory entry need to change.

`learner_id` is part of the signature because Dev C's protocol specifies it,
but it is validated against the learner the tool was built for rather than
trusted: an escalation attributed to the wrong learner would send a trainer to
the wrong person with the wrong context.

A NULL `trainer_id` is explicitly NOT an error. Dev C's route node escalates
even when the upstream trainer lookup failed, on the principle that a learner
who is stuck must never be silently dropped. Those rows land in the
unassigned-escalations queue for the trainer dashboard to pick up.
"""

from __future__ import annotations

import logging
from typing import Callable

from app.agent.repository import AgentRepository
from app.agent.types import EscalationReason, EscalationWriteError

logger = logging.getLogger(__name__)

EscalateToTrainer = Callable[..., int]

# Escalation text is stored verbatim for the trainer dashboard; cap the
# lengths so a runaway model-generated value cannot bloat the row.
MAX_DETAIL_LENGTH = 500
MAX_QUESTION_LENGTH = 4000


def make_escalate_to_trainer(
    repository: AgentRepository,
) -> EscalateToTrainer:
    """Build an `escalate_to_trainer` bound to one learner's repository."""

    def escalate_to_trainer(
        *,
        learner_id: int,
        course_id: int,
        trainer_id: int | None,
        question: str,
        reason: EscalationReason,
        detail: str | None = None,
    ) -> int:
        """
        Write an escalation record and return its id.

        Args:
            learner_id: must match the learner this tool was built for.
            course_id: the course the question was asked against.
            trainer_id: the resolved trainer, or None for the unassigned queue.
            question: the learner's original question, stored verbatim so the
                trainer does not have to ask for it again.
            reason: structured category (no relevant context, model
                uncertainty, policy violation, ...).
            detail: free-form context for the reason, e.g. the top score.

        Returns:
            The new escalation's id.

        Raises:
            EscalationWriteError: on a learner mismatch, invalid input, or a
                failed write. Escalation is the last line of defence for a
                learner who is stuck — it must fail loudly rather than
                silently drop the record.
        """
        if int(learner_id) != repository.learner_id:
            raise EscalationWriteError(
                "Refusing to escalate: learner_id "
                f"{learner_id} does not match the learner this tool is bound "
                f"to ({repository.learner_id})."
            )

        if not question or not question.strip():
            raise EscalationWriteError("Cannot escalate an empty question.")
        if reason is None:
            raise EscalationWriteError("An escalation requires a reason.")

        if trainer_id is None:
            logger.warning(
                "Escalating learner=%s course=%s with no trainer assigned; "
                "row goes to the unassigned queue.",
                repository.learner_id,
                course_id,
            )

        escalation_id = repository.create_escalation(
            course_id=int(course_id),
            question=question.strip()[:MAX_QUESTION_LENGTH],
            reason=reason,
            trainer_id=trainer_id,
            detail=detail.strip()[:MAX_DETAIL_LENGTH] if detail else None,
        )

        logger.info(
            "Escalated to trainer: escalation_id=%s learner=%s course=%s",
            escalation_id,
            repository.learner_id,
            course_id,
        )
        return escalation_id

    return escalate_to_trainer
