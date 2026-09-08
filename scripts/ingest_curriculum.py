"""
Ingest curriculum, resources, assignments, and FAQs into content_embeddings.

PRODUCTION SAFETY -- this is designed to be run repeatedly (e.g. as an
automated step on every deploy) with no manual intervention and no `--clear`:

- Unchanged chunks are left alone entirely -- no re-embed call, no write.
- Changed chunks (source text edited) are updated in place.
- Chunks whose source no longer produces them are deleted.
- `--clear` is kept for local/dev resets only -- never run it against a
  database serving live traffic.

Each source's identity is (content_type, source_type, source_id); each
chunk's identity within that source is chunk_index. content_hash makes
"changed vs. unchanged" detectable without re-embedding.
"""

import argparse
import json
import logging
import os
import sys

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select, SQLModel

from app.agent.content_extraction import (
    build_assignment_full_text,
    build_resource_full_text,
)
from app.agent.embeddings import EmbeddingsClient
from app.agent.ingestion import delete_orphaned_sources, sync_source
from app.agent.types import ASSIGNMENT, CURRICULUM, FAQ, RESOURCE
from app.core.database import engine
from app.features.assignments.model import Assignment
from app.features.lessons.model import Lesson
from app.features.modules.model import Module
from app.features.resources.model import Resource

logger = logging.getLogger("kodebuddy.ingest_curriculum")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest curriculum, resources, assignments, and FAQs into content_embeddings."
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help=(
            "DEV/LOCAL ONLY: wipe content_embeddings before ingesting. Never "
            "run this against a database serving live traffic."
        ),
    )
    parser.add_argument(
        "--faqs",
        type=str,
        default="data/faqs.json",
        help="Path to FAQs JSON file.",
    )
    parser.add_argument(
        "--skip-link-scraping",
        action="store_true",
        help=(
            "Skip fetching resource link URLs (still embeds title/"
            "description). Useful for a fast dry run."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        embed_client = EmbeddingsClient()
    except ValueError as exc:
        logger.error("Failed to initialize embeddings client: %s", exc)
        return

    logger.info(
        "Initialized Embeddings Client (Model: %s, Dimension: %d)",
        embed_client.model,
        embed_client.dimension,
    )

    totals = {"embedded": 0, "updated": 0, "deleted": 0}

    with Session(engine) as session:
        if args.clear:
            logger.warning("Clearing existing content_embeddings (dev/local reset)...")
            session.exec(
                SQLModel.metadata.tables["content_embeddings"].delete()
            )  # type: ignore
            session.commit()

        # ----------------------------------------------------
        # 1. Lessons (Curriculum Content)
        # ----------------------------------------------------
        lessons = session.exec(select(Lesson).where(Lesson.is_active == True)).all()
        logger.info("Found %d active lessons.", len(lessons))

        for lesson in lessons:
            module = session.exec(
                select(Module).where(Module.id == lesson.module_id)
            ).first()
            if not module:
                logger.warning(
                    "Lesson %d has no matching module. Skipping.",
                    lesson.id,
                )
                continue

            full_text = f"Lesson Title: {lesson.title}\nContent: {lesson.content_body or ''}"
            embedded, updated, deleted = sync_source(
                session,
                embed_client,
                course_id=module.course_id,
                module_id=lesson.module_id,
                content_type=CURRICULUM,
                source_type="lesson",
                source_id=lesson.id,
                full_text=full_text,
            )
            totals["embedded"] += embedded
            totals["updated"] += updated
            totals["deleted"] += deleted
            logger.info(
                "Lesson '%s': %d embedded, %d written, %d stale chunks removed.",
                lesson.title,
                embedded,
                updated,
                deleted,
            )

        deleted = delete_orphaned_sources(
            session,
            content_type=CURRICULUM,
            source_type="lesson",
            live_source_ids={lesson.id for lesson in lessons},
        )
        totals["deleted"] += deleted
        if deleted:
            logger.info("Removed %d chunks for lessons no longer active.", deleted)

        # ----------------------------------------------------
        # 2. Resources -- with real link scraping / file parsing / article content
        # ----------------------------------------------------
        resources = session.exec(
            select(Resource).where(Resource.is_active == True)
        ).all()
        logger.info("Found %d active resources.", len(resources))

        for resource in resources:
            module = session.exec(
                select(Module).where(Module.id == resource.module_id)
            ).first()
            if not module:
                logger.warning(
                    "Resource %d has no matching module. Skipping.",
                    resource.id,
                )
                continue

            # Determine resource type
            resource_type = resource.type
            if hasattr(resource_type, "value"):
                type_value = resource_type.value
            else:
                type_value = str(resource_type).lower()

            if args.skip_link_scraping and type_value == "link" and not resource.file_path:
                full_text = f"Resource Title: {resource.title}\nDescription: {resource.description or ''}"
                extract_status, extract_error = None, None
            else:
                extraction = build_resource_full_text(resource)
                full_text = extraction.text
                extract_status, extract_error = extraction.status, extraction.error
                resource.content_extract_status = extract_status
                resource.content_extract_error = extract_error
                session.add(resource)

            embedded, updated, deleted = sync_source(
                session,
                embed_client,
                course_id=module.course_id,
                module_id=resource.module_id,
                content_type=RESOURCE,
                source_type="resource",
                source_id=resource.id,
                full_text=full_text,
            )
            totals["embedded"] += embedded
            totals["updated"] += updated
            totals["deleted"] += deleted
            status_note = f" [{extract_status}]" if extract_status else ""
            logger.info(
                "Resource '%s'%s: %d embedded, %d written, %d stale chunks removed.",
                resource.title,
                status_note,
                embedded,
                updated,
                deleted,
            )
            if extract_error:
                logger.warning("    extraction note: %s", extract_error)

        deleted = delete_orphaned_sources(
            session,
            content_type=RESOURCE,
            source_type="resource",
            live_source_ids={resource.id for resource in resources},
        )
        totals["deleted"] += deleted
        if deleted:
            logger.info("Removed %d chunks for resources no longer active.", deleted)

        session.commit()  # persist content_extract_status/_error before moving on

        # ----------------------------------------------------
        # 3. Assignments
        # ----------------------------------------------------
        assignments = session.exec(
            select(Assignment).where(Assignment.is_active == True)
        ).all()
        logger.info("Found %d active assignments.", len(assignments))

        for assignment in assignments:
            module = session.exec(
                select(Module).where(Module.id == assignment.module_id)
            ).first()
            if not module:
                logger.warning(
                    "Assignment %d has no matching module. Skipping.",
                    assignment.id,
                )
                continue

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
            totals["embedded"] += embedded
            totals["updated"] += updated
            totals["deleted"] += deleted
            logger.info(
                "Assignment '%s': %d embedded, %d written, %d stale chunks removed.",
                assignment.title,
                embedded,
                updated,
                deleted,
            )

        deleted = delete_orphaned_sources(
            session,
            content_type=ASSIGNMENT,
            source_type="assignment",
            live_source_ids={assignment.id for assignment in assignments},
        )
        totals["deleted"] += deleted
        if deleted:
            logger.info("Removed %d chunks for assignments no longer active.", deleted)

        # ----------------------------------------------------
        # 4. FAQs
        # ----------------------------------------------------
        if os.path.exists(args.faqs):
            try:
                with open(args.faqs, "r", encoding="utf-8") as f:
                    faqs = json.load(f)

                logger.info("Found %d FAQs.", len(faqs))
                live_faq_ids = set()
                for faq_idx, faq in enumerate(faqs):
                    course_id = faq.get("course_id")
                    question = faq.get("question")
                    answer = faq.get("answer")

                    if not question or not answer:
                        logger.warning("Invalid FAQ entry at index %d. Skipping.", faq_idx)
                        continue

                    # Prefer a stable id from the FAQ entry itself if present;
                    # fall back to file position only when no id is given.
                    faq_source_id = faq.get("id", faq_idx)
                    live_faq_ids.add(faq_source_id)

                    full_text = f"Frequently Asked Question: {question}\nAnswer: {answer}"
                    embedded, updated, deleted = sync_source(
                        session,
                        embed_client,
                        course_id=course_id,
                        module_id=None,
                        content_type=FAQ,
                        source_type="faq",
                        source_id=faq_source_id,
                        full_text=full_text,
                    )
                    totals["embedded"] += embedded
                    totals["updated"] += updated
                    totals["deleted"] += deleted
                    if embedded or deleted:
                        logger.info(
                            "FAQ '%s': %d embedded, %d written, %d stale chunks removed.",
                            question[:50] + "..." if len(question) > 50 else question,
                            embedded,
                            updated,
                            deleted,
                        )

                deleted = delete_orphaned_sources(
                    session,
                    content_type=FAQ,
                    source_type="faq",
                    live_source_ids=live_faq_ids,
                )
                totals["deleted"] += deleted
                if deleted:
                    logger.info(
                        "Removed %d chunks for FAQs no longer in %s.",
                        deleted,
                        args.faqs,
                    )
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Could not load FAQs from '%s': %s", args.faqs, exc)
        else:
            logger.warning("No FAQs file found at %s. Skipping FAQs ingestion.", args.faqs)

        session.commit()
        logger.info(
            "Ingestion completed: %d chunks embedded (new/changed only), %d rows written, %d stale rows removed.",
            totals["embedded"],
            totals["updated"],
            totals["deleted"],
        )


if __name__ == "__main__":
    main()