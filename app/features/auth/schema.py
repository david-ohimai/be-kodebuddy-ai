from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.features.profile.schema import UserDto

class CreateUser(BaseModel):
    email: EmailStr
    password: str

class LoginUser(BaseModel):
    email: str
    password:str

class LoginResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserDto


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    message: str