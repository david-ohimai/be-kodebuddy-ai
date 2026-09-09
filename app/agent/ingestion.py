"""
Shared ingestion/sync primitives for content_embeddings.

Owner: Dev A (Data & Ingestion) / Dev B (Retrieval & Tools) — shared seam.

WHY THIS MODULE EXISTS
-----------------------
`scripts/ingest_curriculum.py` originally contained the only copy of the
chunk/hash/reconcile logic and was designed to be run out-of-band (cron,
deploy step, or by hand). That is exactly the gap the review flagged:

    "resource creation just persists a DB row and never touches the
    embedding/ingestion pipeline."

Rather than have the API layer shell out to the script (fragile, slow,
hard to test, and impossible to run inside a request/background task),
this module lifts the reconcile-one-source logic out of the script into an
importable unit. The script now imports from here too, so there is exactly
one implementation of "how a source's chunks get reconciled against
content_embeddings" — not two copies that can drift.

WHO CALLS THIS
--------------
- `scripts/ingest_curriculum.py` — full-corpus batch reconciliation (deploy
  step / cron), across lessons, resources, assignments, and FAQs.
- `app.features.resources.services.base_resource_service.BaseResourceService`
  — incremental, single-row sync scheduled as a BackgroundTask on create/update/delete.
- `app.features.assignments.service.AssignmentService` — same, for assignments.

Both incremental callers use `sync_resource_embeddings` /
`sync_assignment_embeddings` below.
"""

from __future__ import annotations

import hashlib
import logging
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlmodel import Session, select

from app.agent.content_extraction import (
    EXTRACT_STATUS_FAILED,
    ExtractionResult,
    build_assignment_full_text,
    build_resource_full_text,
)
from app.agent.embeddings import EmbeddingsClient, get_shared_client
from app.agent.model import ContentEmbedding
from app.agent.types import ASSIGNMENT, CURRICULUM, FAQ, RESOURCE
from app.core.database import engine
from app.features.assignments.model import Assignment
from app.features.modules.model import Module
from app.features.resources.model import Resource

logger = logging.getLogger("kodebuddy.agent.ingestion")


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> List[str]:
    """Splits a body of text into smaller overlapping chunks."""
    if not text or not text.strip():
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(text)


def content_hash(text: str) -> str:
    """Deterministic hash of chunk text, used to detect unchanged content on re-ingest."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sync_source(
    session: Session,
    embed_client: EmbeddingsClient,
    *,
    course_id: int | None,
    module_id: int | None,
    content_type: str,
    source_type: str,
    source_id: int,
    full_text: str,
) -> tuple[int, int, int]:
    """
    Reconciles content_embeddings rows for one source (one lesson, one
    resource, one assignment, or one FAQ) against its freshly-chunked
    current text.

    Returns (embedded_count, updated_count, deleted_count) so the caller
    can report/log what happened — embedded_count is the number of chunks
    that actually hit the embeddings API (new or changed only).

    Passing an empty/blank `full_text` deletes every existing chunk for the
    source and embeds nothing — this is how "the source no longer has any
    extractable content" (a link that failed to scrape, a resource that was
    deactivated) removes stale grounding without a separate code path.
    """
    chunks = chunk_text(full_text)
    new_hashes = [content_hash(c) for c in chunks]

    existing_rows = session.exec(
        select(ContentEmbedding).where(
            ContentEmbedding.content_type == content_type,
            ContentEmbedding.source_type == source_type,
            ContentEmbedding.source_id == source_id,
        )
    ).all()
    existing_by_index = {row.chunk_index: row for row in existing_rows}

    to_embed_indices = [
        idx
        for idx, h in enumerate(new_hashes)
        if existing_by_index.get(idx) is None
        or existing_by_index[idx].content_hash != h
        or existing_by_index[idx].embedding_model != embed_client.model
    ]
    embedded_vectors: dict[int, list[float]] = {}
    if to_embed_indices:
        vectors = embed_client.embed_texts([chunks[i] for i in to_embed_indices])
        embedded_vectors = dict(zip(to_embed_indices, vectors))

    updated_count = 0
    for idx, chunk_body in enumerate(chunks):
        existing = existing_by_index.get(idx)
        h = new_hashes[idx]
        if (
            existing is not None
            and existing.content_hash == h
            and existing.embedding_model == embed_client.model
        ):
            continue  
        if existing is not None:
            existing.text = chunk_body
            existing.content_hash = h
            existing.embedding = embedded_vectors[idx]
            existing.embedding_model = embed_client.model
            session.add(existing)
        else:
            session.add(
                ContentEmbedding(
                    course_id=course_id,
                    module_id=module_id,
                    content_type=content_type,
                    source_type=source_type,
                    source_id=source_id,
                    chunk_index=idx,
                    content_hash=h,
                    embedding_model=embed_client.model,
                    text=chunk_body,
                    embedding=embedded_vectors[idx],
                )
            )
        updated_count += 1

    deleted_count = 0
    for idx, row in existing_by_index.items():
        if idx >= len(chunks):
            session.delete(row)
            deleted_count += 1

    return len(to_embed_indices), updated_count, deleted_count


def delete_source(
    session: Session,
    *,
    content_type: str,
    source_type: str,
    source_id: int,
) -> int:
    """
    Removes every content_embeddings chunk belonging to one source outright.

    Used when a resource/assignment is soft-deleted (`is_active=False`):
    `sync_source` with an empty full_text would achieve the same result,
    but calling this directly avoids an unnecessary extraction attempt
    (fetching a URL, reading a file) for content we're about to discard.
    """
    rows = session.exec(
        select(ContentEmbedding).where(
            ContentEmbedding.content_type == content_type,
            ContentEmbedding.source_type == source_type,
            ContentEmbedding.source_id == source_id,
        )
    ).all()
    for row in rows:
        session.delete(row)
    return len(rows)


def delete_orphaned_sources(
    session: Session,
    *,
    content_type: str,
    source_type: str,
    live_source_ids: set[int],
) -> int:
    """Deletes every content_embeddings row for this content_type/source_type
    whose source_id is no longer in the current live set."""
    existing_source_ids = set(
        session.exec(
            select(ContentEmbedding.source_id).where(
                ContentEmbedding.content_type == content_type,
                ContentEmbedding.source_type == source_type,
            )
        ).all()
    )
    orphaned_ids = existing_source_ids - live_source_ids
    if not orphaned_ids:
        return 0

    rows = session.exec(
        select(ContentEmbedding).where(
            ContentEmbedding.content_type == content_type,
            ContentEmbedding.source_type == source_type,
            ContentEmbedding.source_id.in_(orphaned_ids),
        )
    ).all()
    for row in rows:
        session.delete(row)
    return len(rows)


# --------------------------------------------------------------------------
# Incremental, single-row sync — called from the API layer as a
# FastAPI BackgroundTask (see ResourceService / AssignmentService).
# --------------------------------------------------------------------------


def sync_resource_embeddings(resource_id: int) -> None:
    """
    Reconciles content_embeddings for exactly one resource.

    Opens its own session/engine connection rather than reusing the
    request's, because this runs as a BackgroundTask *after* the HTTP
    response has already been returned to the caller.

    Never raises back into the caller: a scrape failure, a missing API
    key, or a transient DB error must not surface as a 500 on the
    request that scheduled this. Every failure is logged and, where it
    can be attributed to one resource, recorded on that resource's
    `content_extract_status`/`content_extract_error` so admins/trainers can
    see *why* a resource isn't grounding answers.
    """
    try:
        with Session(engine) as session:
            resource = session.get(Resource, resource_id)
            if resource is None:
                logger.warning(
                    "sync_resource_embeddings: resource %s no longer exists; "
                    "removing any orphaned chunks.",
                    resource_id,
                )
                delete_source(
                    session,
                    content_type=RESOURCE,
                    source_type="resource",
                    source_id=resource_id,
                )
                session.commit()
                return

            if not resource.is_active:
                deleted = delete_source(
                    session,
                    content_type=RESOURCE,
                    source_type="resource",
                    source_id=resource.id,
                )
                session.commit()
                logger.info(
                    "sync_resource_embeddings: resource %s inactive -- "
                    "removed %d stale chunk(s).",
                    resource_id,
                    deleted,
                )
                return

            module = session.get(Module, resource.module_id)
            if module is None:
                logger.warning(
                    "sync_resource_embeddings: resource %s has no matching "
                    "module %s; skipping.",
                    resource_id,
                    resource.module_id,
                )
                return

            try:
                embed_client = get_shared_client()
            except ValueError:
                logger.error(
                    "sync_resource_embeddings: embeddings client unavailable "
                    "(missing GEMINI_API_KEY) -- resource %s was NOT "
                    "re-ingested.",
                    resource_id,
                )
                resource.content_extract_status = EXTRACT_STATUS_FAILED
                resource.content_extract_error = "Embeddings provider unavailable."
                session.add(resource)
                session.commit()
                return

            extraction: ExtractionResult = build_resource_full_text(resource)

            embedded, updated, deleted = sync_source(
                session,
                embed_client,
                course_id=module.course_id,
                module_id=resource.module_id,
                content_type=RESOURCE,
                source_type="resource",
                source_id=resource.id,
                full_text=extraction.text,
            )

            resource.content_extract_status = extraction.status
            resource.content_extract_error = extraction.error
            session.add(resource)
            session.commit()

            logger.info(
                "sync_resource_embeddings: resource=%s status=%s embedded=%d "
                "updated=%d deleted=%d",
                resource_id,
                extraction.status,
                embedded,
                updated,
                deleted,
            )
    except Exception: 
        logger.exception(
            "sync_resource_embeddings: unhandled failure for resource_id=%s",
            resource_id,
        )


def sync_assignment_embeddings(assignment_id: int) -> None:
    """
    Reconciles content_embeddings for exactly one assignment.

    Mirrors `sync_resource_embeddings`. Assignment text (title, description,
    instructions, requirements) always comes straight from the DB — there is
    no scrape/parse step that can fail — so this has no equivalent of
    `content_extract_status`.
    """
    try:
        with Session(engine) as session:
            assignment = session.get(Assignment, assignment_id)
            if assignment is None:
                delete_source(
                    session,
                    content_type=ASSIGNMENT,
                    source_type="assignment",
                    source_id=assignment_id,
                )
                session.commit()
                return

            if not assignment.is_active:
                deleted = delete_source(
                    session,
                    content_type=ASSIGNMENT,
                    source_type="assignment",
                    source_id=assignment.id,
                )
                session.commit()
                logger.info(
                    "sync_assignment_embeddings: assignment %s inactive -- "
                    "removed %d stale chunk(s).",
                    assignment_id,
                    deleted,
                )
                return

            module = session.get(Module, assignment.module_id)
            if module is None:
                logger.warning(
                    "sync_assignment_embeddings: assignment %s has no "
                    "matching module %s; skipping.",
                    assignment_id,
                    assignment.module_id,
                )
                return

            try:
                embed_client = get_shared_client()
            except ValueError:
                logger.error(
                    "sync_assignment_embeddings: embeddings client "
                    "unavailable (missing GEMINI_API_KEY) -- assignment %s "
                    "was NOT re-ingested.",
                    assignment_id,
                )
                return

            full_text = build_assignment_full_text(assignment)

            embedded, updated, deleted = sync_source(
                session,
                embed_client,
                course_id=module.course_id,
                module_id=assignment.module_id,
                content_type=ASSIGNMENT,
                source_type="assignment",
                source_id=assignment.id,
                full_text=full_text,
            )
            session.commit()

            logger.info(
                "sync_assignment_embeddings: assignment=%s embedded=%d "
                "updated=%d deleted=%d",
                assignment_id,
                embedded,
                updated,
                deleted,
            )
    except Exception:  # noqa: BLE001 -- background task, must never raise
        logger.exception(
            "sync_assignment_embeddings: unhandled failure for "
            "assignment_id=%s",
            assignment_id,
        )