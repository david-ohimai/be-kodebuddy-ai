# app/core/env.py

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing from the .env file.")

if not AUTH_SECRET_KEY:
    raise ValueError("AUTH_SECRET_KEY is missing from the .env file.")

if not FRONTEND_URL:
    raise ValueError("FRONTEND_URL is missing from the .env file.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)

REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
)

PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "15")
)

VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
VOYAGE_EMBED_MODEL = os.getenv("VOYAGE_EMBED_MODEL", "voyage-3")