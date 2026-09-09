"""
Embeddings client, backed by Gemini's embedding model (gemini-embedding-001).

"""

from __future__ import annotations

import logging
import time
from typing import List

from app.core.config import (
    AGENT_EMBED_DIMENSION,
    AGENT_EMBED_GEMINI_MODEL,
    GEMINI_API_KEY,
)

logger = logging.getLogger("kodebuddy.agent.embeddings")


_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

_TASK_TYPE_BY_INPUT_TYPE = {
    "document": "RETRIEVAL_DOCUMENT",
    "query": "RETRIEVAL_QUERY",
}


def _is_retryable(exc: Exception) -> bool:
    """
    True for capacity/rate-limit errors worth a short backoff + retry.
    Checks the SDK's own status code first (google.genai.errors.APIError
    exposes `.code`), then falls back to name/message heuristics for
    anything that isn't wrapped as an APIError (e.g. a lower-level
    transport error) so a genuinely transient failure of an unexpected
    shape still gets retried rather than immediately failing ingestion or
    a live retrieval request.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, int) and code in _TRANSIENT_STATUS_CODES:
        return True

    name = type(exc).__name__.lower()
    if any(
        marker in name
        for marker in ("ratelimit", "timeout", "connection", "serviceunavailable", "servererror")
    ):
        return True

    message = str(exc).lower()
    return any(
        marker in message
        for marker in ("rate limit", "rate_limit", "429", "503", "too many requests", "unavailable", "high demand")
    )


def _call_with_retry(fn, *args, **kwargs):
    """
    Calls `fn`, retrying up to `_MAX_ATTEMPTS` total attempts with
    exponential backoff (1s, 2s, ...) when the failure looks transient per
    `_is_retryable`. Re-raises immediately on a non-retryable failure, and
    re-raises the last exception once attempts are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc: 
            last_exc = exc
            if attempt == _MAX_ATTEMPTS or not _is_retryable(exc):
                raise
            delay = _RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "Gemini embedding call failed on attempt %d/%d (%s: %s); "
                "retrying in %.1fs.",
                attempt,
                _MAX_ATTEMPTS,
                type(exc).__name__,
                exc,
                delay,
            )
            time.sleep(delay)
    assert last_exc is not None 
    raise last_exc


def _normalize(vector: List[float]) -> List[float]:
    """
    gemini-embedding-001 only pre-normalizes the full 3072-dim output; any
    truncated dimension (which is what this app uses -- see
    AGENT_EMBED_DIMENSION) comes back un-normalized and needs this step
    done manually, or cosine-similarity scores read on pgvector's <=>
    operator will be systematically off. (Google's newer gemini-embedding-2
    normalizes truncated output automatically; -001 does not.)
    """
    norm = sum(x * x for x in vector) ** 0.5
    return [x / norm for x in vector] if norm > 0 else vector


class EmbeddingsClient:
    """Wrapper around Gemini's embedding model (gemini-embedding-001)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        from google import genai  

        resolved_key = api_key or GEMINI_API_KEY
        if not resolved_key:
            raise ValueError(
                "GEMINI_API_KEY is not set -- EmbeddingsClient refuses to "
                "start rather than silently falling back to meaningless "
                "placeholder vectors. Set GEMINI_API_KEY (the same key "
                "used for the chat LLM) to embed for real, or pass an "
                "explicit test double in tests instead of constructing "
                "this class."
            )

        self._client = genai.Client(api_key=resolved_key)
        self.model = model or AGENT_EMBED_GEMINI_MODEL
        self.dimension = dimension or AGENT_EMBED_DIMENSION

    def embed_text(self, text: str, input_type: str = "document") -> List[float]:
        """Embeds a single piece of text.

        Args:
            text: The text string to embed.
            input_type: The type of context ("document" or "query").

        Returns:
            A list of floats representing the embedding vector.
        """
        return self.embed_texts([text], input_type=input_type)[0]

    def embed_texts(
        self, texts: List[str], input_type: str = "document"
    ) -> List[List[float]]:
        """Embeds a list of texts.

        Args:
            texts: A list of text strings to embed.
            input_type: The type of context ("document" or "query").

        Returns:
            A list of list of floats representing the embedding vectors.
        """
        if not texts:
            return []

        from google.genai import types

        task_type = _TASK_TYPE_BY_INPUT_TYPE.get(input_type, "RETRIEVAL_DOCUMENT")

        response = _call_with_retry(
            self._client.models.embed_content,
            model=self.model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=self.dimension,
            ),
        )
        return [_normalize(e.values) for e in response.embeddings]


_client: "EmbeddingsClient | None" = None


def _get_client() -> "EmbeddingsClient":
    """Reuse one client across calls instead of re-initializing on every
    single query."""
    global _client
    if _client is None:
        _client = EmbeddingsClient()
    return _client


def get_shared_client() -> "EmbeddingsClient":
    """
    Public accessor for the process-wide shared EmbeddingsClient.

    Added so callers outside this module that need document-side embedding
    (e.g. app.agent.ingestion's incremental resource/assignment sync, in
    addition to scripts/ingest_curriculum.py which previously constructed
    its own client) can reuse the same cached instance and the same
    "raise loudly if GEMINI_API_KEY is missing" behaviour, instead of each
    caller constructing its own `EmbeddingsClient()` -- one obvious call
    site keeps that error message consistent everywhere it can occur.
    """
    return _get_client()


def embed_query(text: str) -> List[float]:
    """
    Embed a single search query.

    input_type="query" matters: Gemini embeds queries and documents
    slightly differently to improve retrieval quality, and everything
    ingested via ingest_curriculum.py used input_type="document".
    """
    return _get_client().embed_text(text, input_type="query")