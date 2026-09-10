import logging

import openai
from google.genai import errors as genai_errors
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
    except openai.AuthenticationError as exc:
        logger.exception("Agent LLM authentication failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Agent LLM is misconfigured (authentication failed).",
        ) from exc
    except openai.RateLimitError as exc:
        logger.warning("Agent LLM rate-limited: %s", exc)
        raise HTTPException(
            status_code=429,
            detail="Agent is temporarily rate-limited. Try again shortly.",
        ) from exc
    except openai.APIConnectionError as exc:
        logger.exception("Could not reach agent LLM provider: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach the agent's LLM provider.",
        ) from exc
    except openai.APIStatusError as exc:
        logger.exception(
            "Agent LLM provider returned status %s: %s", exc.status_code, exc
        )
        raise HTTPException(
            status_code=502,
            detail=f"Agent LLM provider error: {exc.status_code}.",
        ) from exc
    except genai_errors.APIError as exc:
        logger.exception(
            "Agent LLM provider returned status %s: %s",
            getattr(exc, "code", None),
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Agent LLM provider error: {getattr(exc, 'code', None)}.",
        ) from exc
    except Exception as exc:
        logger.exception("Unhandled agent error: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="The agent could not process this request.",
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