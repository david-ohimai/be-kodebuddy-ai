"""
Production LLMClient implementations, backed by real LLM providers, plus a
fallback wrapper that chains several of them together.

Owner: Dev D (Service & API)

Satisfies app.agent.graph.contracts.LLMClient: complete(system, user) -> str.
This is the only place in the codebase that calls a real LLM provider for
the chat/assignment-guidance request path. scripts/agent_tools_demo.py (Dev
B's standalone harness) uses its own tool-calling loop and does not share
this client -- that script exercises retrieval tools directly, not the graph,
and still uses the `anthropic` package independently of what's wired in here.

STRUCTURED OUTPUT: nodes.py's `_parse_llm_response` expects
{"answer": str, "uncertain": bool} back from `complete()`. Previously the
*only* thing enforcing that shape was prose instruction #5 in the system
prompt (prompts/chat.py / prompts/assignment_guidance.py) -- neither Gemini
nor OpenRouter guarantees a model actually follows a "respond with only this
JSON shape" instruction, especially under the fallback chain where a
smaller/cheaper model may be answering. Both clients below now ask their
provider to *enforce* the shape at generation time (Gemini's
response_schema, OpenRouter/OpenAI's response_format json_schema) instead of
relying on the model choosing to comply. If the specific underlying model
doesn't support that constraint, the request is retried once without it, so
a single unsupported model doesn't hard-fail the tier -- nodes.py's parser
remains the last line of defence either way.
"""

from __future__ import annotations

import logging
import time

from app.core.config import (
    AGENT_LLM_GEMINI_MAX_TOKENS,
    AGENT_LLM_GEMINI_MODEL,
    AGENT_LLM_OPENROUTER_MAX_TOKENS,
    AGENT_LLM_OPENROUTER_MODEL,
    GEMINI_API_KEY,
    OPENROUTER_API_KEY,
)

logger = logging.getLogger("kodebuddy.agent.llm")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Shared JSON Schema for the {"answer": str, "uncertain": bool} contract
# nodes.py._parse_llm_response expects. Defined once here so both clients
# (and anyone adding a third provider later) enforce exactly the same shape.
_RESPONSE_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "The answer to show the learner. Plain text; light markdown is fine.",
        },
        "uncertain": {
            "type": "boolean",
            "description": (
                "True if you are not genuinely confident this answer is "
                "correct and fully supported by the given context."
            ),
        },
    },
    "required": ["answer", "uncertain"],
    "additionalProperties": False,
}


class GeminiLLMClient:
    """
    Thin wrapper around a single-turn Gemini completion, using Google's
    current `google-genai` SDK (the older `google-generativeai` package is
    deprecated -- it raises a FutureWarning telling you to switch, and
    receives no further updates or bug fixes).

    Requires GEMINI_API_KEY and AGENT_LLM_GEMINI_MODEL set -- construction
    succeeds either way (matching the lazy-failure style used throughout
    this module), and the first real call fails with the SDK's own error if
    either is missing/invalid.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        from google import genai  

        self._client = genai.Client(api_key=api_key or GEMINI_API_KEY)
        self._model = model or AGENT_LLM_GEMINI_MODEL
        self._max_tokens = max_tokens or AGENT_LLM_GEMINI_MAX_TOKENS

    _TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
    _TRANSIENT_RETRY_DELAY_SECONDS = 2.0

    @classmethod
    def _is_transient(cls, exc: Exception) -> bool:
        """
        True for capacity/rate-limit errors (e.g. 503 UNAVAILABLE / "high
        demand", 429 rate limit) where retrying the *same* request is the
        right move. False for errors that are actually about this specific
        request/config -- e.g. a 400 INVALID_ARGUMENT because this
        model/account tier rejects response_schema -- which should be
        retried without the schema instead, not against a timer.
        """
        return getattr(exc, "code", None) in cls._TRANSIENT_STATUS_CODES

    def complete(self, *, system: str, user: str) -> str:
        from google.genai import errors, types

        structured_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "answer": types.Schema(type=types.Type.STRING),
                "uncertain": types.Schema(type=types.Type.BOOLEAN),
            },
            required=["answer", "uncertain"],
        )

        config_with_schema = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self._max_tokens,
            response_mime_type="application/json",
            response_schema=structured_schema,
        )
        config_without_schema = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=self._max_tokens,
        )

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user,
                config=config_with_schema,
            )
        except errors.APIError as exc:
            if self._is_transient(exc):
                logger.warning(
                    "Gemini model %s hit a transient error (%s: %s); "
                    "retrying same request after %.1fs backoff.",
                    self._model,
                    type(exc).__name__,
                    exc,
                    self._TRANSIENT_RETRY_DELAY_SECONDS,
                )
                time.sleep(self._TRANSIENT_RETRY_DELAY_SECONDS)
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=user,
                    config=config_with_schema,
                )
            else:
                logger.warning(
                    "Gemini model %s rejected structured-output config "
                    "(%s: %s); retrying without response_schema "
                    "enforcement.",
                    self._model,
                    type(exc).__name__,
                    exc,
                )
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=user,
                    config=config_without_schema,
                )
        except Exception as exc:
            logger.warning(
                "Gemini model %s raised a non-API error (%s: %s); "
                "retrying without response_schema enforcement.",
                self._model,
                type(exc).__name__,
                exc,
            )
            response = self._client.models.generate_content(
                model=self._model,
                contents=user,
                config=config_without_schema,
            )

        return (response.text or "").strip()


class OpenRouterLLMClient:
    """
    Thin wrapper around a single-turn completion via OpenRouter.

    OpenRouter's API is OpenAI-compatible, so this uses the `openai`
    Python package as the client library -- pointed at OpenRouter's
    base_url with an OpenRouter API key, never OpenAI's own endpoint or
    OPENAI_API_KEY. OpenRouter model strings are "provider/model" (e.g.
    "anthropic/claude-3.5-haiku", "meta-llama/llama-3.1-8b-instruct") --
    see openrouter.ai/models for what's available on your account/credits.

    Genuinely useful as a fallback tier: OpenRouter itself proxies to many
    underlying providers, so this can act as a single integration point
    for several backup models without adding more SDKs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        import openai

        self._client = openai.OpenAI(
            api_key=api_key or OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self._model = model or AGENT_LLM_OPENROUTER_MODEL
        self._max_tokens = max_tokens or AGENT_LLM_OPENROUTER_MAX_TOKENS

    def complete(self, *, system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "kodebuddy_agent_response",
                        "strict": True,
                        "schema": _RESPONSE_JSON_SCHEMA,
                    },
                },
            )
        except Exception as exc: 
            logger.warning(
                "OpenRouter model %s rejected response_format=json_schema "
                "(%s: %s); retrying with json_object mode.",
                self._model,
                type(exc).__name__,
                exc,
            )
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
            except Exception as exc2:  # noqa: BLE001
                logger.warning(
                    "OpenRouter model %s also rejected response_format="
                    "json_object (%s: %s); retrying with no response_format.",
                    self._model,
                    type(exc2).__name__,
                    exc2,
                )
                response = self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    messages=messages,
                )

        return (response.choices[0].message.content or "").strip()


class FallbackLLMClient:
    """
    Tries a list of LLMClient-shaped objects in order, returning the first
    one that succeeds. Exists so a single provider hiccup (rate limit,
    transient outage, model overload) doesn't turn into a failed request
    for the learner when a second provider/model could have answered.

    Deliberately catches broadly (`Exception`, not just known transient
    error types): a bad JSON parse, an SDK-internal error, or an error type
    this module hasn't seen yet should all still trigger a fallback attempt
    rather than propagating immediately -- the cost of trying the next
    client is one extra network call, not a wrong answer.

    """

    def __init__(self, clients: list) -> None:
        if not clients:
            raise ValueError("FallbackLLMClient needs at least one client.")
        self._clients = clients

    def complete(self, *, system: str, user: str) -> str:
        last_exc: Exception | None = None
        for i, client in enumerate(self._clients):
            try:
                return client.complete(system=system, user=user)
            except Exception as exc:  # noqa: BLE001 -- see docstring
                last_exc = exc
                logger.warning(
                    "LLM client %d/%d (%s) failed: %s: %s -- %s",
                    i + 1,
                    len(self._clients),
                    type(client).__name__,
                    type(exc).__name__,
                    exc,
                    "trying next" if i + 1 < len(self._clients) else "no more fallbacks",
                )
        assert last_exc is not None  # unreachable if clients is non-empty
        raise last_exc


__all__ = ["GeminiLLMClient", "OpenRouterLLMClient", "FallbackLLMClient"]