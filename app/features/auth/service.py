
from fastapi import HTTPException

from app.core.security import hash_password
from app.features.profile.schema import UserDto, UserResponse
from app.features.cohorts.repository.repository import CohortRepository
from app.features.cohorts.repository.cohort_assign_repo import CohortAssignRepository
from .model import User, UserRole
from .repository import AuthRepository
from .schema import (
    CreateUser,
)


class AuthService:

    def __init__(
        self,
        repository: AuthRepository,
        cohort_repository: CohortRepository,
        cohort_assign_repository: CohortAssignRepository,
    ):
        self.repository = repository
        self.cohort_repository = cohort_repository
        self.cohort_assign_repository = cohort_assign_repository



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

        # Find the current/open cohort
        current_cohort = self.cohort_repository.get_current_cohort()

        if current_cohort is None:
            raise HTTPException(
                status_code=400,
                detail="There is no open cohort available for registration.",
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

        # Automatically assign learner to current cohort
        self.cohort_assign_repository.assign_learner(
            cohort_id=current_cohort.id,
            learner_id=db_user.id,
        )


        return UserResponse(
            message="User created successfully",
            user=UserDto.model_validate(db_user),
        )

  