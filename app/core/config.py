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

# --- agent LLM (Dev D) ---
# Deliberately NOT validated at import time like DATABASE_URL/AUTH_SECRET_KEY
# above: every module that imports app.core.config (which is most of the
# app) would otherwise fail to import in any environment/test run that
# doesn't need the LLM. A missing/invalid key surfaces instead as a clear
# anthropic.AuthenticationError at the first real call, in app/agent/llm.py.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
AGENT_LLM_MODEL = os.getenv("AGENT_LLM_MODEL", "claude-opus-5")
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
AGENT_LLM_FALLBACK_MODEL = os.getenv(
    "AGENT_LLM_FALLBACK_MODEL", "claude-haiku-4-5-20251001"
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# No default -- set to whatever Gemini model your API key has access to
# (e.g. "gemini-2.5-flash").
AGENT_LLM_GEMINI_MODEL = os.getenv("AGENT_LLM_GEMINI_MODEL", "")
AGENT_LLM_GEMINI_MAX_TOKENS = int(os.getenv("AGENT_LLM_GEMINI_MAX_TOKENS", "2048"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# OpenRouter model strings are "provider/model", e.g. "anthropic/claude-3.5-haiku"
# or "meta-llama/llama-3.1-8b-instruct". Check openrouter.ai/models for what's
# actually available on your account/credits.
AGENT_LLM_OPENROUTER_MODEL = os.getenv("AGENT_LLM_OPENROUTER_MODEL", "")
AGENT_LLM_OPENROUTER_MAX_TOKENS = int(
    os.getenv("AGENT_LLM_OPENROUTER_MAX_TOKENS", "2048")
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# No default -- set to whatever model your Groq account has access to
# (e.g. "llama-3.3-70b-versatile").
AGENT_LLM_GROQ_MODEL = os.getenv("AGENT_LLM_GROQ_MODEL", "")
AGENT_LLM_GROQ_MAX_TOKENS = int(os.getenv("AGENT_LLM_GROQ_MAX_TOKENS", "2048"))