from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.auth import get_current_admin
from app.core.session import get_session
from app.features.auth.model import User

from .schema import (
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    InviteUserRequest,
    InviteUserResponse,
)
from .service import (
    accept_invitation_service,
    invite_user_service,
)


router = APIRouter(
    prefix="/user/invitations",
    tags=["User Invitations"],
)


@router.post(
    "",
    response_model=InviteUserResponse,
)
def invite_user(
    data: InviteUserRequest,
    current_admin: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    return invite_user_service(
        data,
        current_admin,
        session,
    )


@router.post(
    "/accept",
    response_model=AcceptInvitationResponse,
)
def accept_invitation(
    data: AcceptInvitationRequest,
    session: Session = Depends(get_session),
):
    return accept_invitation_service(
        data,
        session,
    )