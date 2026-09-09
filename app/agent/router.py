import logging

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.agent.graph.state import EscalationReason
from app.agent.repository import AgentRepository, ConversationHistoryRepository
from app.agent.service import (
    NotEnrolledError,
    answer_assignment_guidance,
    answer_chat_question,
)
from app.agent.types import EscalationWriteError
from app.core.auth import get_current_learner
from app.core.session import get_session
from app.features.auth.model import User
from app.features.courses.model import CourseTrainer
from app.features.notifications.repository import NotificationRepository
from app.features.notifications.service import NotificationService
from app.features.escalations.repository import EscalationRepository
from app.features.escalations.schema import EscalationCreate, EscalationResponse

from .schema import (
    AgentTurnResponse,
    ConversationTurnResponse,
    HistoryResponse,
    MessageRequest,
)

router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)

logger = logging.getLogger("kodebuddy.agent.router")


def get_history_repository(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_learner),
) -> ConversationHistoryRepository:
    return ConversationHistoryRepository(session, learner_id=current_user.id)


def _handle_agent_errors(fn, *args, **kwargs):
    """
    Shared exception-to-HTTP-status mapping for the agent endpoint below.

    NotEnrolledError/EscalationWriteError are this app's own domain
    exceptions (service.py, app.agent.types respectively); the anthropic.*
    exceptions mirror the mapping already established in Dev B's
    scripts/agent_tools_demo.py harness, applied here to the real request
    path instead of a CLI script.
    """
    try:
        return fn(*args, **kwargs)
    except NotEnrolledError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except EscalationWriteError as exc:
        logger.exception("Escalation write failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Failed to record an escalation for this question.",
        ) from exc
    except anthropic.AuthenticationError as exc:
        logger.exception("Agent LLM authentication failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Agent LLM is misconfigured (authentication failed).",
        ) from exc
    except anthropic.RateLimitError as exc:
        logger.warning("Agent LLM rate-limited: %s", exc)
        raise HTTPException(
            status_code=429,
            detail="Agent is temporarily rate-limited. Try again shortly.",
        ) from exc
    except anthropic.APIConnectionError as exc:
        logger.exception("Could not reach agent LLM provider: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach the agent's LLM provider.",
        ) from exc
    except anthropic.APIStatusError as exc:
        logger.exception(
            "Agent LLM provider returned status %s: %s", exc.status_code, exc
        )
        raise HTTPException(
            status_code=502,
            detail=f"Agent LLM provider error: {exc.status_code}.",
        ) from exc


@router.post(
    "/chat",
    response_model=AgentTurnResponse,
)
def chat(
    body: MessageRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_learner),
):
    """
    Single entry point for the agent chat. Routes to assignment guidance
    ("guide, don't solve", grounded in the structured assignment brief)
    when the caller supplies assignment_id, or general curriculum/FAQ chat
    otherwise. Scoped to the requesting learner via `get_current_learner`
    -- there is no way to ask on another learner's behalf.

    The routing decision lives here, not in schema.py or service.py: the
    request shape (MessageRequest) stays a plain data container, and
    service.py keeps its two distinct entry points
    (answer_chat_question/answer_assignment_guidance) because they still
    genuinely differ inside (query_type, whether get_assignment_brief runs
    at all) -- this function is the one place that decides which of those
    two a given request means.
    """
    if body.assignment_id is not None:
        result = _handle_agent_errors(
            answer_assignment_guidance,
            session,
            learner_id=current_user.id,
            course_id=body.course_id,
            module_id=body.module_id,
            assignment_id=body.assignment_id,
            question=body.question,
        )
    else:
        result = _handle_agent_errors(
            answer_chat_question,
            session,
            learner_id=current_user.id,
            course_id=body.course_id,
            module_id=body.module_id,
            question=body.question,
        )
    return AgentTurnResponse(**result.__dict__)


@router.post(
    "/escalate",
    response_model=EscalationResponse,
)
def create_escalation(
    body: EscalationCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_learner),
):
    """
    Direct learner-triggered escalation -- what the frontend's "Escalate to
    trainer" button calls, after a chat turn came back with
    AgentTurnResponse.escalation_available=True.

    Was previously an untyped `dict` body returning a hand-built `dict` --
    now a real typed contract (`EscalationCreate` in/`EscalationResponse`
    out, both app/features/escalations/schema.py) shared with the
    trainer-facing GET endpoints in app/features/escalations/router.py, so
    a caller gets proper 422 validation instead of a KeyError-shaped 500,
    and gets back the full row it just created (including whatever
    module_id/assignment_id/draft_response/confidence_score it sent),
    rather than a bespoke five-key summary.

    `module_id`, `assignment_id`, `draft_response`, and `confidence_score`
    are all optional and, when this is called right after a chat turn,
    should be the same values the frontend already received on that turn's
    request (module_id/assignment_id) and response
    (draft_response/confidence_score) -- round-tripped, not re-typed by the
    learner or re-derived here.
    """
    reason_value = body.reason.strip()
    try:
        reason = EscalationReason(reason_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid escalation reason: {reason_value}",
        ) from exc

    repository = AgentRepository(session, learner_id=current_user.id)
    if not repository.is_enrolled(body.course_id):
        raise HTTPException(
            status_code=403,
            detail=f"Learner {current_user.id} is not enrolled in course {body.course_id}.",
        )

    trainer_row = session.exec(
        select(CourseTrainer)
        .where(CourseTrainer.course_id == body.course_id)
        .order_by(CourseTrainer.id)
    ).first()
    trainer_id = trainer_row.trainer_id if trainer_row is not None else None

    escalation_id = repository.create_escalation(
        course_id=body.course_id,
        module_id=body.module_id,
        assignment_id=body.assignment_id,
        question=body.question,
        reason=reason,
        trainer_id=trainer_id,
        detail=body.detail,
        draft_response=body.draft_response,
        confidence_score=body.confidence_score,
    )

    notification_service = NotificationService(NotificationRepository(session))
    notification_service.notify_escalation_created(
        learner_id=current_user.id,
        trainer_id=trainer_id,
        escalation_id=escalation_id,
        course_id=body.course_id,
        reason=reason.value,
    )

    escalation = EscalationRepository(session).get_by_id(escalation_id)
    return EscalationResponse.model_validate(escalation)


@router.get(
    "/history",
    response_model=HistoryResponse,
)
def get_history(
    course_id: int | None = Query(default=None),
    module_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: ConversationHistoryRepository = Depends(get_history_repository),
):
    """
    Returns the current user's own conversation history with the agent,
    newest first. Scoped to the requesting user via `get_current_learner` --
    there is no way to pass another learner's id in, matching the RBAC
    pattern used for retrieval in app/agent/repository.py.
    """
    rows, total = repository.get_page(
        course_id=course_id,
        module_id=module_id,
        limit=limit,
        offset=offset,
    )
    return HistoryResponse(
        turns=[ConversationTurnResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )