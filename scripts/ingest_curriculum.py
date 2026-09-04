"""
Ingest curriculum, resources, and FAQs into content_embeddings.

PRODUCTION SAFETY -- this is designed to be run repeatedly (e.g. as an
automated step on every deploy, whenever data/faqs.json or the
lessons/resources tables change) with no manual intervention and no
`--clear`:

- Unchanged chunks are left alone entirely -- no re-embed call, no write.
  This matters because content_embeddings backs *live* queries; wiping it
  with `--clear` means a window where retrieval returns nothing, and
  re-embedding unchanged text burns real API calls/rate-limit budget for
  zero benefit (see app/agent/embeddings.py's docstring on Voyage's
  free-tier rate limits).
- Changed chunks (source text edited) are updated in place.
- Chunks whose source no longer produces them (edited to be shorter, or a
  lesson/resource/FAQ removed or deactivated) are deleted, so stale
  content stops grounding answers.
- `--clear` is kept for local/dev resets only -- never run it against a
  database serving live traffic.

Each source's identity is (content_type, source_type, source_id); each
chunk's identity within that source is chunk_index. content_hash (already
in the schema, previously unused) is what makes "changed vs. unchanged"
detectable without re-embedding to compare.
"""

import argparse
import hashlib
import json
import os
import sys
from typing import List

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlmodel import Session, select, SQLModel

from app.agent.embeddings import EmbeddingsClient
from app.agent.model import ContentEmbedding
from app.core.database import engine
from app.features.lessons.model import Lesson
from app.features.modules.model import Module
from app.features.resources.model import Resource


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> List[str]:
    """Splits a body of text into smaller overlapping chunks."""
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
    resource, or one FAQ) against its freshly-chunked current text.

    Returns (embedded_count, updated_count, deleted_count) so the caller
    can print a summary -- embedded_count is the number of chunks that
    actually hit the embeddings API (i.e. new or changed only), which is
    the number worth watching for API cost/rate-limit purposes.
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

    # Chunks that are new, whose text changed, OR whose stored vector came
    # from a *different embedding model* all need an embeddings API call --
    # batch them together in one request rather than one call per chunk.
    # The model check matters even when text_hash is unchanged: switching
    # embedding providers (e.g. Voyage -> Gemini) puts vectors in a
    # completely different vector space, so an old vector next to a new
    # query vector produces meaningless cosine similarity even though
    # nothing about the source text changed. Without this check, a
    # provider swap would silently leave every untouched chunk stale.
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
            continue  # unchanged, same model -- leave the row exactly as-is
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

    # Any existing chunk_index beyond the new chunk count belongs to text
    # that used to be longer -- delete it so a stale tail chunk can't keep
    # grounding answers.
    deleted_count = 0
    for idx, row in existing_by_index.items():
        if idx >= len(chunks):
            session.delete(row)
            deleted_count += 1

    return len(to_embed_indices), updated_count, deleted_count


def delete_orphaned_sources(
    session: Session,
    *,
    content_type: str,
    source_type: str,
    live_source_ids: set[int],
) -> int:
    """
    Deletes every content_embeddings row for this content_type/source_type
    whose source_id is no longer in the current live set -- covers a
    lesson/resource being deactivated or a FAQ being removed from the
    JSON file entirely (sync_source alone only catches a source's chunk
    *count* shrinking, not the whole source disappearing).
    """
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


def main():
    parser = argparse.ArgumentParser(
        description="Ingest curriculum, resources, and FAQs into content_embeddings."
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help=(
            "DEV/LOCAL ONLY: wipe content_embeddings before ingesting. Never "
            "run this against a database serving live traffic -- it opens a "
            "window where retrieval returns nothing, and re-embeds unchanged "
            "content for no benefit. Production runs should omit this flag "
            "entirely; the script is idempotent and change-aware without it."
        ),
    )
    parser.add_argument(
        "--faqs",
        type=str,
        default="data/faqs.json",
        help="Path to FAQs JSON file.",
    )
    args = parser.parse_args()

    # No mock mode anymore -- this raises immediately with a clear message
    # if GEMINI_API_KEY isn't set, rather than silently proceeding with
    # meaningless vectors.
    embed_client = EmbeddingsClient()
    print(
        f"Initialized Embeddings Client (Model: {embed_client.model}, "
        f"Dimension: {embed_client.dimension})"
    )

    totals = {"embedded": 0, "updated": 0, "deleted": 0}

    with Session(engine) as session:
        if args.clear:
            print("Clearing existing content_embeddings (dev/local reset)...")
            session.exec(
                SQLModel.metadata.tables["content_embeddings"].delete()
            )  # type: ignore
            session.commit()

        # ----------------------------------------------------
        # 1. Lessons (Curriculum Content)
        # ----------------------------------------------------
        lessons = session.exec(select(Lesson).where(Lesson.is_active == True)).all()
        print(f"Found {len(lessons)} active lessons.")

        for lesson in lessons:
            module = session.exec(
                select(Module).where(Module.id == lesson.module_id)
            ).first()
            if not module:
                print(f"Warning: Lesson {lesson.id} has no matching module. Skipping.")
                continue

            full_text = f"Lesson Title: {lesson.title}\nContent: {lesson.content_body or ''}"
            embedded, updated, deleted = sync_source(
                session,
                embed_client,
                course_id=module.course_id,
                module_id=lesson.module_id,
                content_type="curriculum",
                source_type="lesson",
                source_id=lesson.id,
                full_text=full_text,
            )
            totals["embedded"] += embedded
            totals["updated"] += updated
            totals["deleted"] += deleted
            print(
                f"Lesson '{lesson.title}': {embedded} embedded, "
                f"{updated} written, {deleted} stale chunks removed."
            )

        deleted = delete_orphaned_sources(
            session,
            content_type="curriculum",
            source_type="lesson",
            live_source_ids={lesson.id for lesson in lessons},
        )
        totals["deleted"] += deleted
        if deleted:
            print(f"Removed {deleted} chunks for lessons no longer active.")

        # ----------------------------------------------------
        # 2. Resources
        # ----------------------------------------------------
        resources = session.exec(
            select(Resource).where(Resource.is_active == True)
        ).all()
        print(f"Found {len(resources)} active resources.")

        for resource in resources:
            module = session.exec(
                select(Module).where(Module.id == resource.module_id)
            ).first()
            if not module:
                print(f"Warning: Resource {resource.id} has no matching module. Skipping.")
                continue

            full_text = (
                f"Resource Title: {resource.title}\n"
                f"Description: {resource.description or ''}\n"
                f"Link URL: {resource.url}"
            )
            embedded, updated, deleted = sync_source(
                session,
                embed_client,
                course_id=module.course_id,
                module_id=resource.module_id,
                content_type="resource",
                source_type="resource",
                source_id=resource.id,
                full_text=full_text,
            )
            totals["embedded"] += embedded
            totals["updated"] += updated
            totals["deleted"] += deleted
            print(
                f"Resource '{resource.title}': {embedded} embedded, "
                f"{updated} written, {deleted} stale chunks removed."
            )

        deleted = delete_orphaned_sources(
            session,
            content_type="resource",
            source_type="resource",
            live_source_ids={resource.id for resource in resources},
        )
        totals["deleted"] += deleted
        if deleted:
            print(f"Removed {deleted} chunks for resources no longer active.")

        # ----------------------------------------------------
        # 3. FAQs
        # ----------------------------------------------------
        if os.path.exists(args.faqs):
            print(f"Loading FAQs from {args.faqs}...")
            try:
                with open(args.faqs, "r", encoding="utf-8") as f:
                    faqs = json.load(f)

                print(f"Found {len(faqs)} FAQs.")
                live_faq_ids = set()
                for faq_idx, faq in enumerate(faqs):
                    course_id = faq.get("course_id")
                    question = faq.get("question")
                    answer = faq.get("answer")

                    if not question or not answer:
                        print(f"Warning: Invalid FAQ entry {faq}. Skipping.")
                        continue

                    # Prefer a stable id from the FAQ entry itself if present;
                    # fall back to file position only when no id is given.
                    # Pure file position is brittle (shifts if entries are
                    # reordered/inserted) -- add a stable "id" to each FAQ
                    # entry in the JSON as soon as you can, so re-ingests
                    # after reordering don't misattribute rows.
                    faq_source_id = faq.get("id", faq_idx)
                    live_faq_ids.add(faq_source_id)

                    full_text = f"Frequently Asked Question: {question}\nAnswer: {answer}"
                    embedded, updated, deleted = sync_source(
                        session,
                        embed_client,
                        course_id=course_id,
                        module_id=None,
                        content_type="faq",
                        source_type="faq",
                        source_id=faq_source_id,
                        full_text=full_text,
                    )
                    totals["embedded"] += embedded
                    totals["updated"] += updated
                    totals["deleted"] += deleted
                    if embedded or deleted:
                        print(
                            f"FAQ '{question}': {embedded} embedded, "
                            f"{updated} written, {deleted} stale chunks removed."
                        )

                deleted = delete_orphaned_sources(
                    session,
                    content_type="faq",
                    source_type="faq",
                    live_source_ids=live_faq_ids,
                )
                totals["deleted"] += deleted
                if deleted:
                    print(f"Removed {deleted} chunks for FAQs no longer in {args.faqs}.")
            except Exception as e:
                print(f"Error loading FAQs: {e}")
        else:
            print(f"No FAQs file found at {args.faqs}. Skipping FAQs ingestion.")

        session.commit()
        print(
            f"Ingestion completed: {totals['embedded']} chunks embedded "
            f"(new/changed only), {totals['updated']} rows written, "
            f"{totals['deleted']} stale rows removed."
        )


if __name__ == "__main__":
    main()