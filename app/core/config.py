# app/core/env.py

import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing from the .env file.")

if not AUTH_SECRET_KEY:
    raise ValueError("AUTH_SECRET_KEY is missing from the .env file.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(60)