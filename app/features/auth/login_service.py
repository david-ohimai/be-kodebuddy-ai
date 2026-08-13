from datetime import timedelta

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlmodel import Session, select

from app.core.config import ALGORITHM, AUTH_SECRET_KEY
from app.core.email import send_reset_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.features.auth.model import User
from app.features.auth.schema import ForgotPasswordRequest, ForgotPasswordResponse, LoginResponse, LoginUser, RefreshTokenRequest, RefreshTokenResponse, ResetPasswordRequest, ResetPasswordResponse
from app.features.profile.schema import UserDto


def login_user(
    login_data: LoginUser,
    session: Session,
):
    statement = select(User).where(
        User.email == login_data.email
    )

    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )


    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
        )

    if not verify_password(
        login_data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    token_data = {
        "sub": user.email,
        "user_id": user.id,
        "role": user.role.value,
    }

    access_token = create_access_token(
        token_data
    )

    refresh_token = create_refresh_token(
        token_data
    )

    return LoginResponse(
        message="Login successful",
        user=UserDto.model_validate(user),
        access_token=access_token,
        refresh_token=refresh_token,
    )


async def forgot_password_service(data: ForgotPasswordRequest, session: Session):
    user = session.exec(
        select(User).where(User.email == data.email)
    ).first()

    if not user:
        return ForgotPasswordResponse(
            message="If an account with that email exists, a password reset link has been sent."
        )

    reset_token = create_access_token(
        {
            "sub": user.email,
            "purpose": "password_reset",
        },
        expires_delta=timedelta(minutes=60),
    )

    await send_reset_email(
        user.email,
        reset_token,
    )
    return ForgotPasswordResponse(
        message="If an account with that email exists, a password reset link has been sent."
    )


def reset_password_service(data: ResetPasswordRequest, session: Session):
    try:
        payload = jwt.decode(
            data.token,
            AUTH_SECRET_KEY,
            algorithms=[ALGORITHM],
        )

    except JWTError:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired token",
        )

    if payload.get("purpose") != "password_reset":
        raise HTTPException(
            status_code=400,
            detail="Invalid token",
        )

    email = payload["sub"]

    user = session.exec(
        select(User).where(User.email == email)
    ).first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user.hashed_password = hash_password(data.new_password)

    session.add(user)
    session.commit()

    return ResetPasswordResponse(
        message="Password reset successful."
    )

def refresh_access_token(
    data: RefreshTokenRequest,
    session: Session,
):
    try:
        payload = jwt.decode(
            data.refresh_token,
            AUTH_SECRET_KEY,
            algorithms=[ALGORITHM],
        )

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    user_id = payload.get("user_id")

    if user_id is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    user = session.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is inactive",
        )

    token_data = {
        "sub": user.email,
        "user_id": user.id,
        "role": user.role.value,
    }

    new_access_token = create_access_token(
        token_data
    )

    new_refresh_token = create_refresh_token(
        token_data
    )

    return RefreshTokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


