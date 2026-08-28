"""
Production LLMClient implementations, backed by real LLM providers, plus a
fallback wrapper that chains several of them together.

Owner: Dev D (Service & API)

Satisfies app.agent.graph.contracts.LLMClient: complete(system, user) -> str.
This is the only place in the codebase that calls a real LLM provider for
the chat/assignment-guidance request path. scripts/agent_tools_demo.py (Dev
B's standalone harness) uses its own tool-calling loop and does not share
this client -- that script exercises retrieval tools directly, not the graph.
"""

from __future__ import annotations

import logging

import anthropic

from app.core.config import (
    AGENT_LLM_FALLBACK_MODEL,
    AGENT_LLM_GEMINI_MAX_TOKENS,
    AGENT_LLM_GEMINI_MODEL,
    AGENT_LLM_GROQ_MAX_TOKENS,
    AGENT_LLM_GROQ_MODEL,
    AGENT_LLM_MAX_TOKENS,
    AGENT_LLM_MODEL,
    AGENT_LLM_OPENROUTER_MAX_TOKENS,
    AGENT_LLM_OPENROUTER_MODEL,
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    GROQ_API_KEY,
    OPENROUTER_API_KEY,
)

logger = logging.getLogger("kodebuddy.agent.llm")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class AnthropicLLMClient:
    """
    Thin wrapper around a single-turn Anthropic completion.

    No retries/backoff here on purpose: app.agent.graph.nodes.reason has no
    concept of "the LLM call failed", only "the LLM's response didn't parse"
    (see nodes.py::_parse_llm_response's fail-safe behaviour, which handles
    a malformed *response*, not a raised exception). Retry-across-providers
    behaviour lives one layer up, in FallbackLLMClient below -- this class
    stays a plain single-call wrapper so it's still usable on its own (e.g.
    in tests, or as one link in a fallback chain).

    Also usable as a same-provider fallback tier: construct a second
    instance with a different `model` (e.g. a smaller/cheaper model) to
    fall back to if your primary model is rate-limited or overloaded,
    without leaving Anthropic entirely.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        # anthropic.Anthropic() also reads ANTHROPIC_API_KEY from the
        # environment itself, but passing it explicitly keeps this class's
        # dependency on app.core.config visible and testable.
        self._client = anthropic.Anthropic(api_key=api_key or ANTHROPIC_API_KEY)
        self._model = model or AGENT_LLM_MODEL
        self._max_tokens = max_tokens or AGENT_LLM_MAX_TOKENS

    def complete(self, *, system: str, user: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()


class GeminiLLMClient:
    """
    Thin wrapper around a single-turn Gemini completion, using Google's
    current `google-genai` SDK (the older `google-generativeai` package is
    deprecated -- it raises a FutureWarning telling you to switch, and
    receives no further updates or bug fixes).

    Requires GEMINI_API_KEY and AGENT_LLM_GEMINI_MODEL set -- construction
    succeeds either way (matching AnthropicLLMClient's lazy-failure style),
    and the first real call fails with the SDK's own error if either is
    missing/invalid.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        from google import genai  # imported here so a missing `google-genai`
        # package only breaks callers that actually construct this client.

        self._client = genai.Client(api_key=api_key or GEMINI_API_KEY)
        self._model = model or AGENT_LLM_GEMINI_MODEL
        self._max_tokens = max_tokens or AGENT_LLM_GEMINI_MAX_TOKENS

    def complete(self, *, system: str, user: str) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=self._max_tokens,
            ),
        )
        return (response.text or "").strip()


class GroqLLMClient:
    """
    Thin wrapper around a single-turn Groq chat completion. Groq's client
    library mirrors the OpenAI SDK shape (chat.completions.create with
    messages=[...]), but this is Groq's own `groq` package talking to
    Groq's own endpoint -- useful mainly for fast/cheap inference on hosted
    open models, as a distinct failure domain from both Anthropic and
    Gemini.

    Requires GROQ_API_KEY and AGENT_LLM_GROQ_MODEL set.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> None:
        from groq import Groq  # imported here so a missing `groq` package
        # only breaks callers that actually construct this client.

        self._client = Groq(api_key=api_key or GROQ_API_KEY)
        self._model = model or AGENT_LLM_GROQ_MODEL
        self._max_tokens = max_tokens or AGENT_LLM_GROQ_MAX_TOKENS

    def complete(self, *, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (response.choices[0].message.content or "").strip()


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
        import openai  # imported here so a missing `openai` package only
        # breaks callers that actually construct this client.

        self._client = openai.OpenAI(
            api_key=api_key or OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self._model = model or AGENT_LLM_OPENROUTER_MODEL
        self._max_tokens = max_tokens or AGENT_LLM_OPENROUTER_MAX_TOKENS

    def complete(self, *, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
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

    Caveat worth knowing before you rely on this for the demo:
    app/agent/router.py's exception handling only has explicit mappings
    for `anthropic.*` exception types today. If EVERY client in this chain
    fails, this re-raises whatever the LAST one raised -- so if your last
    fallback tier is Gemini, Groq, or OpenRouter and it also fails, that
    error won't match any of router.py's `except anthropic.*` clauses and
    will surface as a generic unhandled 500 instead of one of the friendly
    mapped messages. Put an Anthropic client last if you want router.py's
    existing mapping to still apply on total failure, or widen router.py's
    exception handling later to cover the other providers' error types --
    happy to make that change when you get there.
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


__all__ = [
    "AnthropicLLMClient",
    "GeminiLLMClient",
    "GroqLLMClient",
    "OpenRouterLLMClient",
    "FallbackLLMClient",
]