from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.auth import get_current_user
from app.core.session import get_session
from app.features.auth.model import User

from .repository import ConversationHistoryRepository
from .schema import ConversationTurnResponse, HistoryResponse

router = APIRouter(
    prefix="/agent",
    tags=["Agent"],
)


def get_history_repository(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConversationHistoryRepository:
    return ConversationHistoryRepository(session, learner_id=current_user.id)


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
    newest first. Scoped to the requesting user via `get_current_user` —
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
