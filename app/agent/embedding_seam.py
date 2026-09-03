"""
Seam between Dev B's retrieval layer and Dev A's embedding module.

Owner: Dev B (Retrieval & Tools)

Dev A owns `app/agent/embeddings.py` (the Voyage wrapper). That module does not
exist yet, so importing it at module scope would break every import of this
package. Instead we resolve it lazily, at first use, and fail with a message
that names the missing piece and its owner.

CONTRACT WITH DEV A
-------------------
`app.agent.embeddings` must expose a callable::

    def embed_query(text: str) -> Sequence[float]: ...

returning a single embedding vector whose dimensionality matches the
`content_embeddings.embedding` column. If the real function ends up with a
different name, add an alias in `embeddings.py` or change
`_EMBED_FUNCTION_NAMES` below — the rest of the retrieval layer does not need
to know.

For local development before that module lands, set
`AGENT_FAKE_EMBEDDINGS=1` to use a deterministic stub. It produces stable
vectors so RBAC and SQL wiring can be exercised end to end, but the similarity
ordering it yields is meaningless — never enable it outside local testing.

QUERY-LEVEL CACHE
------------------
Every graph turn calls this module's `embed_query` twice with the *identical*
text: once from `tools/search_curriculum.py`, once from `tools/search_faqs.py`
(both are handed the learner's raw question — see nodes.py::retrieve). That
was two real Voyage API calls per turn for one embedding, which matters a lot
on a rate-limited account: it halves the number of requests available before
a transient rate-limit failure turns into an unnecessary auto-escalation (see
`_embed_query_cached` below, and app/agent/embeddings.py for the retry side of
that same fix). `embed_query` now memoizes on the exact, whitespace-trimmed
query text — an in-process cache, not persisted anywhere, and bounded so it
can't grow unbounded over a long-running process. Only successful lookups are
cached; a failure is never memoized, so a transient failure on one call still
gets a fresh attempt on the very next one, not a cached exception.
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import struct
from functools import lru_cache
from typing import Callable, Sequence

from app.agent.types import EmbeddingUnavailableError

logger = logging.getLogger(__name__)

# Names tried, in order, when looking for Dev A's embedding entry point.
_EMBED_FUNCTION_NAMES = ("embed_query", "embed_text", "embed")

# Dimensionality of the stub vectors. Only used when AGENT_FAKE_EMBEDDINGS=1.
_FAKE_EMBEDDING_DIM = 1024

# Bounds the query-level embedding cache described in the module docstring.
# Sized for "the same question embedded twice within one turn" (the actual
# problem this fixes), not as a long-lived semantic cache -- 256 distinct
# in-flight query strings is generous headroom for that without holding
# onto memory indefinitely across a long process lifetime.
_EMBED_CACHE_SIZE = 256

_cached_embedder: Callable[[str], Sequence[float]] | None = None


def _fake_embed(text: str) -> list[float]:
    """
    Deterministic pseudo-embedding for local development.

    Seeded from a SHA-256 digest of the text and L2-normalised so that cosine
    distance stays in its usual range. Same text always yields the same vector.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < _FAKE_EMBEDDING_DIM:
        block = hashlib.sha256(digest + struct.pack(">I", counter)).digest()
        # 8 bytes -> one float in [-1, 1), 8 floats per 64-byte block.
        for offset in range(0, len(block), 8):
            chunk = block[offset : offset + 8]
            (raw,) = struct.unpack(">Q", chunk)
            values.append((raw / (2**63)) - 1.0)
            if len(values) == _FAKE_EMBEDDING_DIM:
                break
        counter += 1

    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:  # unreachable in practice, guards against a zero vector
        return values
    return [value / norm for value in values]


def _resolve_embedder() -> Callable[[str], Sequence[float]]:
    """Locate Dev A's embedding callable, or the stub if explicitly enabled."""
    if os.getenv("AGENT_FAKE_EMBEDDINGS") == "1":
        logger.warning(
            "AGENT_FAKE_EMBEDDINGS=1 — using deterministic stub embeddings. "
            "Similarity ranking is meaningless; local development only."
        )
        return _fake_embed

    try:
        from app.agent import embeddings as embeddings_module
    except ImportError as exc:
        raise EmbeddingUnavailableError(
            "app/agent/embeddings.py is not available yet (owned by Dev A — "
            "Data & Ingestion). Set AGENT_FAKE_EMBEDDINGS=1 to run the "
            "retrieval layer against deterministic stub vectors locally."
        ) from exc

    for name in _EMBED_FUNCTION_NAMES:
        candidate = getattr(embeddings_module, name, None)
        if callable(candidate):
            logger.debug("Resolved embedding function app.agent.embeddings.%s", name)
            return candidate

    raise EmbeddingUnavailableError(
        "app/agent/embeddings.py exists but exposes none of "
        f"{_EMBED_FUNCTION_NAMES}. Dev B's retrieval layer needs a callable "
        "taking a string and returning a sequence of floats."
    )


@lru_cache(maxsize=_EMBED_CACHE_SIZE)
def _embed_query_cached(text: str) -> tuple[float, ...]:
    """
    Does the actual embed-and-validate work, keyed by exact query text.

    `functools.lru_cache` only memoizes a *successful* return — if this
    raises, nothing is cached and the next call (even with the same text)
    recomputes from scratch. That's exactly the behaviour wanted here: a
    transient provider failure must never get "cached" as a permanent one.
    """
    global _cached_embedder
    if _cached_embedder is None:
        _cached_embedder = _resolve_embedder()

    try:
        vector = _cached_embedder(text)
    except EmbeddingUnavailableError:
        raise
    except Exception as exc:  # provider-specific failures (HTTP, auth, quota)
        raise EmbeddingUnavailableError(
            f"Embedding provider failed for query: {exc}"
        ) from exc

    if vector is None or len(vector) == 0:
        raise EmbeddingUnavailableError(
            "Embedding provider returned an empty vector."
        )

    return tuple(vector)


def embed_query(text: str) -> Sequence[float]:
    """
    Embed a single search query.

    Raises:
        EmbeddingUnavailableError: if no provider can be resolved, the query is
            blank, or the provider itself fails. Never returns an empty vector,
            because a caller cannot distinguish that from "no matches".
    """
    if not text or not text.strip():
        raise EmbeddingUnavailableError("Cannot embed an empty query.")

    return list(_embed_query_cached(text.strip()))


def reset_embedder_cache() -> None:
    """Clear the memoised provider and the query-level embedding cache.
    Intended for tests."""
    global _cached_embedder
    _cached_embedder = None
    _embed_query_cached.cache_clear()


def to_pgvector_literal(vector: Sequence[float]) -> str:
    """
    Render a vector as the string literal pgvector accepts, e.g. ``[0.1,0.2]``.

    Passed as a *bound parameter* and cast to ``vector`` inside the SQL, so the
    value is never interpolated into the statement text.
    """
    return "[" + ",".join(repr(float(value)) for value in vector) + "]"