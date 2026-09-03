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

# --- agent embeddings ---
# Reuses GEMINI_API_KEY (defined below, also used for the chat LLM) --
# one Gemini API key covers both. No silent fallback mode: EmbeddingsClient
# raises immediately at construction if this is missing, rather than
# degrading into meaningless placeholder vectors (see the removed mock-mode
# path this replaces).
AGENT_EMBED_GEMINI_MODEL = os.getenv("AGENT_EMBED_GEMINI_MODEL", "gemini-embedding-001")
# Must match content_embeddings.embedding's pgvector column width
# (Vector(1024) in app/agent/model.py). gemini-embedding-001 defaults to
# 3072 dims and supports truncating down via Matryoshka Representation
# Learning (MRL) -- 1024 keeps the existing schema/no migration needed.
# Google's own benchmarks specifically validate 768/1536/3072; 1024 is
# supported but untested by them, so if you ever run a fresh migration
# it's worth considering 768 or 1536 instead. Changing this value changes
# the embedding space -- every existing row needs re-embedding, which
# scripts/ingest_curriculum.py now detects and handles automatically.
AGENT_EMBED_DIMENSION = int(os.getenv("AGENT_EMBED_DIMENSION", "1024"))

# --- agent LLM (Dev D) ---
# Deliberately NOT validated at import time like DATABASE_URL/AUTH_SECRET_KEY
# above: every module that imports app.core.config (which is most of the
# app) would otherwise fail to import in any environment/test run that
# doesn't need the LLM. A missing/invalid key surfaces instead as a clear
# anthropic.AuthenticationError at the first real call, in app/agent/llm.py.
AGENT_LLM_MAX_TOKENS = int(os.getenv("AGENT_LLM_MAX_TOKENS", "2048"))
# Windowed chat history size fed into the prompt (see
# app.agent.graph.nodes.AgentDependencies.max_history_turns). Also read by
# Dev E's history_service.load_chat_history call in app/agent/service.py, so
# the number of turns loaded from the DB always matches the number the graph
# is configured to actually use.
AGENT_MAX_HISTORY_TURNS = int(os.getenv("AGENT_MAX_HISTORY_TURNS", "6"))
# --- agent LLM fallback chain (Dev D) ---
# Same "don't validate at import time" reasoning as ANTHROPIC_API_KEY above:
# a missing key here should only break the fallback client that needs it
# when it's actually reached, not every module that imports app.core.config.

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AGENT_LLM_GEMINI_MODEL = os.getenv("AGENT_LLM_GEMINI_MODEL", "")
AGENT_LLM_GEMINI_MAX_TOKENS = int(os.getenv("AGENT_LLM_GEMINI_MAX_TOKENS", "2048"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
AGENT_LLM_OPENROUTER_MODEL = os.getenv("AGENT_LLM_OPENROUTER_MODEL", "")
AGENT_LLM_OPENROUTER_MAX_TOKENS = int(
    os.getenv("AGENT_LLM_OPENROUTER_MAX_TOKENS", "2048")
)