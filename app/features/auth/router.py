from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.session import get_session
from app.features.auth.login_service import forgot_password_service, login_user, refresh_access_token, reset_password_service
from app.features.profile.schema import UserResponse
from app.features.cohorts.repository.repository import CohortRepository
from app.features.cohorts.repository.cohort_assign_repo import CohortAssignRepository

from .repository import AuthRepository
from .schema import (
    CreateUser,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginResponse,
    LoginUser,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from .service import AuthService


router = APIRouter(
    prefix="/user",
    tags=["User"],
)


def get_auth_service(
    session: Session = Depends(get_session),
) -> AuthService:
    auth_repository = AuthRepository(session)
    cohort_repository = CohortRepository(session)
    cohort_assign_repository = CohortAssignRepository(session)

    return AuthService(
        repository=auth_repository,
        cohort_repository=cohort_repository,
        cohort_assign_repository=cohort_assign_repository,
    )


@router.post(
    "/register",
    response_model=UserResponse,
)
def create_user(
    data: CreateUser,
    service: AuthService = Depends(get_auth_service),
):
    return service.create_user(data)


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    data: LoginUser,
    session: Session = Depends(get_session),
):
    return login_user(data, session)



@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
)
def refresh_token(
    data: RefreshTokenRequest,
    session: Session = Depends(get_session),
):
    return refresh_access_token(
        data,
        session,
    )

@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
)
async def forgot_password(
    data: ForgotPasswordRequest,
    session: Session = Depends(get_session),
):
    return await forgot_password_service(data, session)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
)
def reset_password(
    data: ResetPasswordRequest,
    session: Session = Depends(get_session),
):
    return reset_password_service(data, session)

