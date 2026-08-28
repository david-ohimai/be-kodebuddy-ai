from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.features.auth.model import UserRole


class InviteUserRequest(BaseModel):
    email: EmailStr
    role: UserRole
    full_name: str | None = Field(
        default=None,
        max_length=100,
    )


class InviteUserResponse(BaseModel):
    message: str
    email: EmailStr
    role: UserRole
    expires_at: datetime


class AcceptInvitationRequest(BaseModel):
    token: str
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class AcceptInvitationResponse(BaseModel):
    message: str