from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel
from app.features.auth.model import UserRole


class InvitationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"


class UserInvitation(SQLModel, table=True):
    __tablename__ = "user_invitations"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    email: str = Field(
        index=True,
        max_length=255,
    )

    full_name: str | None = Field(
        default=None,
        max_length=100,
    )

    role: UserRole = Field(
        max_length=20,
    )

    token: str = Field(
        unique=True,
        index=True,
        max_length=255,
    )

    expires_at: datetime

    accepted_at: datetime | None = None

    invited_by: int = Field(
        foreign_key="users.id",
        index=True,
    )

    status: InvitationStatus = Field(
        default=InvitationStatus.PENDING,
        max_length=20,
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )