from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.features.auth.model import UserRole



class UpdateProfile(BaseModel):
    full_name: str | None = None


class UserDto(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class UserResponse(BaseModel):
    message: str
    user: UserDto


class UpdateUserRole(BaseModel):
    role: UserRole


