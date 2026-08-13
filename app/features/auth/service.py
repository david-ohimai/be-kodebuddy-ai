
from fastapi import HTTPException

from app.core.security import hash_password
from app.features.profile.schema import UserDto, UserResponse

from .model import User, UserRole
from .repository import AuthRepository
from .schema import (
    CreateUser,
)


class AuthService:

    def __init__(self, repository: AuthRepository):
        self.repository = repository




    def create_user(
        self,
        create_user: CreateUser,
    ) -> UserResponse:

        existing_user = self.repository.get_by_email(
            create_user.email
        )

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="User with that email already exists",
            )

        db_user = User(
            email=create_user.email,
            hashed_password=hash_password(
                create_user.password
            ),
            role=UserRole.LEARNER,
            is_active=True,
        )

        self.repository.create(db_user)

        return UserResponse(
            message="User created successfully",
            user=UserDto.model_validate(db_user),
        )

  