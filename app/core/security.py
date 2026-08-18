
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from jose import jwt
from pwdlib import PasswordHash
from app.core.config import (
    AUTH_SECRET_KEY,
    ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
load_dotenv()


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )

def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({
        "exp": expire,
        "type": "access",
    })

    return jwt.encode(
        to_encode,
        AUTH_SECRET_KEY,
        algorithm=ALGORITHM,
    )


def create_refresh_token(
    data: dict,
    expires_delta: timedelta | None = None,
):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    to_encode.update({
        "exp": expire,
        "type": "refresh",
    })

    return jwt.encode(
        to_encode,
        AUTH_SECRET_KEY,
        algorithm=ALGORITHM,
    )