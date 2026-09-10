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
    if not text or not text.strip():
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(text)


def content_hash(text: str) -> str:
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


def sync_resource_embeddings(resource_id: int) -> None:
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

            resource.content_extract_status = extraction.status
            resource.content_extract_error = extraction.error
            session.add(resource)
            session.commit()

            try:
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
            except Exception as exc:
                logger.exception(
                    "sync_resource_embeddings: embedding sync failed for "
                    "resource_id=%s",
                    resource_id,
                )
                resource.content_extract_status = EXTRACT_STATUS_FAILED
                resource.content_extract_error = f"Embedding sync failed: {exc}"
                session.add(resource)
                session.commit()
                return

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
    except Exception:
        logger.exception(
            "sync_assignment_embeddings: unhandled failure for "
            "assignment_id=%s",
            assignment_id,
        )