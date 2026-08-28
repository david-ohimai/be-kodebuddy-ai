import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.security import hash_password
from app.features.auth.model import User, UserRole

from .model import InvitationStatus, UserInvitation
from .repository import InvitationRepository
from .schema import (
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    InviteUserRequest,
    InviteUserResponse,
)


INVITATION_EXPIRE_HOURS = 24


def invite_user_service(
    data: InviteUserRequest,
    current_admin: User,
    session: Session,
) -> InviteUserResponse:

    if data.role not in {
        UserRole.TRAINER,
        UserRole.MENTOR,
    }:
        raise HTTPException(
            status_code=400,
            detail="Only trainers and mentors can be invited",
        )

    existing_user = session.exec(
        select(User).where(
            User.email == data.email
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists",
        )

    existing_invitation = session.exec(
        select(UserInvitation).where(
            UserInvitation.email == data.email,
            UserInvitation.status == InvitationStatus.PENDING,
        )
    ).first()

    if existing_invitation:
        raise HTTPException(
            status_code=409,
            detail="A pending invitation already exists for this email",
        )

    now = datetime.now(timezone.utc)

    expires_at = now + timedelta(
        hours=INVITATION_EXPIRE_HOURS
    )

    token = secrets.token_urlsafe(32)

    invitation = UserInvitation(
        email=data.email,
        full_name=data.full_name,
        role=data.role.value,
        token=token,
        expires_at=expires_at,
        invited_by=current_admin.id,
        status=InvitationStatus.PENDING,
    )

    repository = InvitationRepository(session)

    repository.create(invitation)

    # Email integration will be added here.
    #
    # Example:
    #
    # await send_invitation_email(
    #     invitation.email,
    #     invitation.token,
    #     invitation.role,
    # )

    return InviteUserResponse(
        message="Invitation created successfully",
        email=invitation.email,
        role=UserRole(invitation.role),
        expires_at=invitation.expires_at,
    )


def accept_invitation_service(
    data: AcceptInvitationRequest,
    session: Session,
) -> AcceptInvitationResponse:

    repository = InvitationRepository(session)

    invitation = repository.get_by_token(
        data.token
    )

    if not invitation:
        raise HTTPException(
            status_code=400,
            detail="Invalid invitation token",
        )

    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail="Invitation has already been used",
        )

    now = datetime.now(timezone.utc)

    expires_at = invitation.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    if expires_at < now:
        invitation.status = InvitationStatus.EXPIRED

        repository.update(invitation)

        raise HTTPException(
            status_code=400,
            detail="Invitation has expired",
        )

    existing_user = session.exec(
        select(User).where(
            User.email == invitation.email
        )
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="A user with this email already exists",
        )

    try:
        role = UserRole(invitation.role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid invitation role",
        )

    if role not in {
        UserRole.TRAINER,
        UserRole.MENTOR,
    }:
        raise HTTPException(
            status_code=400,
            detail="Invalid invitation role",
        )

    user = User(
        email=invitation.email,
        hashed_password=hash_password(
            data.password
        ),
        role=role,
        is_active=True,
        full_name=invitation.full_name,
    )

    session.add(user)

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = now

    session.add(invitation)

    session.commit()

    return AcceptInvitationResponse(
        message=(
            "Invitation accepted successfully. "
            "You can now sign in with your email and password."
        )
    )