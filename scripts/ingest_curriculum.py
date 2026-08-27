import argparse
import json
import os
import sys
from typing import List

# Setup path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlmodel import Session, select

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


def main():
    parser = argparse.ArgumentParser(
        description="Ingest curriculum, resources, and FAQs into content_embeddings."
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the content_embeddings table before ingesting.",
    )
    parser.add_argument(
        "--faqs",
        type=str,
        default="data/faqs.json",
        help="Path to FAQs JSON file.",
    )
    args = parser.parse_args()

    # Initialize Embeddings Client
    embed_client = EmbeddingsClient()
    print(
        f"Initialized Embeddings Client (Mock Mode: {embed_client.is_mock}, Model: {embed_client.model})"
    )

    with Session(engine) as session:
        if args.clear:
            print("Clearing existing content_embeddings...")
            session.exec(
                SQLModel.metadata.tables["content_embeddings"].delete()
            )  # type: ignore
            session.commit()

        # ----------------------------------------------------
        # 1. Ingest Lessons (Curriculum Content)
        # ----------------------------------------------------
        lessons = session.exec(select(Lesson).where(Lesson.is_active == True)).all()
        print(f"Found {len(lessons)} active lessons.")

        for lesson in lessons:
            # Find the module to retrieve the course_id
            module = session.exec(
                select(Module).where(Module.id == lesson.module_id)
            ).first()
            if not module:
                print(
                    f"Warning: Lesson {lesson.id} has no matching module. Skipping."
                )
                continue

            full_text = f"Lesson Title: {lesson.title}\nContent: {lesson.content_body or ''}"
            chunks = chunk_text(full_text)

            print(
                f"Processing Lesson '{lesson.title}' ({len(chunks)} chunks)..."
            )
            embeddings = embed_client.embed_texts(chunks)

            for chunk_text_body, vector in zip(chunks, embeddings):
                record = ContentEmbedding(
                    course_id=module.course_id,
                    module_id=lesson.module_id,
                    content_type="curriculum",
                    text=chunk_text_body,
                    embedding=vector,
                )
                session.add(record)

        # ----------------------------------------------------
        # 2. Ingest Resources
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
                print(
                    f"Warning: Resource {resource.id} has no matching module. Skipping."
                )
                continue

            full_text = (
                f"Resource Title: {resource.title}\n"
                f"Description: {resource.description or ''}\n"
                f"Link URL: {resource.url}"
            )
            chunks = chunk_text(full_text)

            print(
                f"Processing Resource '{resource.title}' ({len(chunks)} chunks)..."
            )
            embeddings = embed_client.embed_texts(chunks)

            for chunk_text_body, vector in zip(chunks, embeddings):
                record = ContentEmbedding(
                    course_id=module.course_id,
                    module_id=resource.module_id,
                    content_type="resource",
                    text=chunk_text_body,
                    embedding=vector,
                )
                session.add(record)

        # ----------------------------------------------------
        # 3. Ingest FAQs
        # ----------------------------------------------------
        if os.path.exists(args.faqs):
            print(f"Loading FAQs from {args.faqs}...")
            try:
                with open(args.faqs, "r", encoding="utf-8") as f:
                    faqs = json.load(f)

                print(f"Found {len(faqs)} FAQs.")
                for faq in faqs:
                    course_id = faq.get("course_id")
                    question = faq.get("question")
                    answer = faq.get("answer")

                    if not question or not answer:
                        print(f"Warning: Invalid FAQ entry {faq}. Skipping.")
                        continue

                    full_text = f"Frequently Asked Question: {question}\nAnswer: {answer}"
                    chunks = chunk_text(full_text)
                    scope = f"course {course_id}" if course_id else "global"
                    print(
                        f"Processing FAQ '{question}' ({len(chunks)} chunks)..."
                    )
                    embeddings = embed_client.embed_texts(chunks)

                    for chunk_text_body, vector in zip(chunks, embeddings):
                        record = ContentEmbedding(
                            course_id=course_id,
                            module_id=None,
                            content_type="faq",
                            text=chunk_text_body,
                            embedding=vector,
                        )
                        session.add(record)
            except Exception as e:
                print(f"Error loading FAQs: {e}")
        else:
            print(
                f"No FAQs file found at {args.faqs}. Skipping FAQs ingestion."
            )

        session.commit()
        print("Ingestion completed successfully!")


if __name__ == "__main__":
    from sqlmodel import SQLModel  # Needed for clearing tables reference
    main()
