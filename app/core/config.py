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

AGENT_EMBED_GEMINI_MODEL = os.getenv("AGENT_EMBED_GEMINI_MODEL", "gemini-embedding-001")

AGENT_EMBED_DIMENSION = int(os.getenv("AGENT_EMBED_DIMENSION", "1024"))
AGENT_LLM_MAX_TOKENS = int(os.getenv("AGENT_LLM_MAX_TOKENS", "2048"))
AGENT_MAX_HISTORY_TURNS = int(os.getenv("AGENT_MAX_HISTORY_TURNS", "6"))
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AGENT_LLM_GEMINI_MODEL = os.getenv("AGENT_LLM_GEMINI_MODEL", "")
AGENT_LLM_GEMINI_MAX_TOKENS = int(os.getenv("AGENT_LLM_GEMINI_MAX_TOKENS", "2048"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
AGENT_LLM_OPENROUTER_MODEL = os.getenv("AGENT_LLM_OPENROUTER_MODEL", "minimax/minimax-m3:free")
AGENT_LLM_OPENROUTER_MAX_TOKENS = int(
    os.getenv("AGENT_LLM_OPENROUTER_MAX_TOKENS", "2048")
)