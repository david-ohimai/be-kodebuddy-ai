# app/features/auth/model.py

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class UserRole(str, Enum):
    LEARNER = "learner"
    TRAINER = "trainer"
    MENTOR = "mentor"
    ADMIN = "admin"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    email: str = Field(
        unique=True,
        index=True,
        max_length=255,
    )

    hashed_password: str

    role: UserRole = Field(
        default=UserRole.LEARNER,
    )

    is_active: bool = True

    full_name: str | None = Field(
        default=None,
        max_length=100,
    )

    profile_picture: str | None = Field(
        default=None,
        max_length=500,
    )

    created_at: datetime = Field(
    default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )