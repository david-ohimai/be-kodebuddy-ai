"""
Small, dependency-free accessor helpers used to defensively read fields off
objects whose exact shape isn't fully in Dev C's control — retrieved chunks
from Dev B's tools, and chat turns from Dev E's history module.

Why this exists: the pinned contracts (RetrievedChunk, ChatTurn TypedDicts
in state.py) are the agreed shape, but TypedDicts aren't enforced at
runtime. A chunk keyed `content`/`similarity_score` instead of
`text`/`score`, or a chat turn keyed `content` instead of `message` (e.g. a
LangChain-style message object), would otherwise raise a raw
KeyError/AttributeError deep inside prompt assembly. These helpers try the
agreed key(s) first and fall back to common alternates, so minor schema
drift degrades gracefully instead of crashing the graph mid-request.

This is a safety net, not a substitute for the pinned contract — if Dev B's
tools or Dev E's history module consistently return a different shape,
that's still a contracts.py conversation, not something to paper over
forever.
"""

from __future__ import annotations

from typing import Any


def get_field(obj: Any, *names: str, default: Any = None) -> Any:
    """Returns the first present value among `names`, checking dict keys
    first, then object attributes."""
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
        elif hasattr(obj, name):
            return getattr(obj, name)
    return default


def chunk_text(chunk: Any) -> str:
    return str(get_field(chunk, "text", "content", default=""))


def chunk_score(chunk: Any) -> float:
    return float(get_field(chunk, "score", "similarity_score", default=0.0))


def chat_turn_role(turn: Any) -> str:
    return str(get_field(turn, "role", "type", default="user"))


def chat_turn_message(turn: Any) -> str:
    return str(get_field(turn, "message", "content", default=""))

def chat_turn_retrieved_assignment_content(turn: Any) -> bool:
    return bool(get_field(turn, "retrieved_assignment_content", default=False))