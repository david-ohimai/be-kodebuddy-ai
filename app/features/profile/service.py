from datetime import datetime, timezone
from fastapi import HTTPException

from app.core.email import send_role_change_email
from app.features.auth.model import User
from app.features.profile.schema import (
    UpdateProfile,
    UpdateUserRole,
    UserDto,
    UserResponse,
)
from app.features.profile.repository import ProfileRepository


class ProfileService:

    def __init__(self, repository: ProfileRepository):
        self.repository = repository


    def get_all_users(self) -> list[UserDto]:

        users = self.repository.get_all()

        return [
            UserDto.model_validate(user)
            for user in users
        ]


    def get_user_by_id(
        self,
        user_id: int,
    ) -> UserDto:

        user = self.repository.get_by_id(user_id)

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        return UserDto.model_validate(user)

    def update_profile(
        self,
        user: User,
        profile_data: UpdateProfile,
    ) -> UserResponse:

        update_data = profile_data.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(user, field, value)

        user.updated_at = datetime.now(timezone.utc)

        updated_user = self.repository.update(user)

        return UserResponse(
            message="Profile updated successfully",
            user=UserDto.model_validate(updated_user),
        )


    async def update_user_role(
        self,
        user_id: int,
        data: UpdateUserRole,
    ) -> UserResponse:

        user = self.repository.get_by_id(user_id)

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )
        
        
        old_role = user.role
        new_role = data.role

        user.role = new_role
        user.updated_at = datetime.now(timezone.utc)

        updated_user = self.repository.update(user)

        if old_role != new_role:
            await send_role_change_email(
                email=updated_user.email,
                first_name=updated_user.first_name,
                new_role=updated_user.role.value,
            )

        return UserResponse(
            message="User role updated successfully",
            user=UserDto.model_validate(updated_user),
        )