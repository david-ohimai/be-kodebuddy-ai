import uuid
from datetime import date

from sqlmodel import Session, select

from app.core.database import engine
from app.agent.embeddings import EmbeddingsClient
from app.agent.model import ContentEmbedding, Escalation, ConversationHistory, QueryLog
from app.agent.graph.state import ChatRole, EscalationReason, QueryType
from app.features.auth.model import User, UserRole
from app.features.cohorts.models.model import Cohort
from app.features.courses.model import Course


def test_embeddings_client_mock_mode(monkeypatch):
    """Verify that EmbeddingsClient mock mode generates valid, deterministic
    embeddings of length 1024."""
    monkeypatch.setattr("app.agent.embeddings.VOYAGE_API_KEY", "mock_key")
    client = EmbeddingsClient()
    assert client.is_mock is True

    text1 = "Hello, testing embeddings."
    text2 = "Hello, testing embeddings."
    text3 = "Different text content."

    vector1 = client.embed_text(text1)
    vector2 = client.embed_text(text2)
    vector3 = client.embed_text(text3)

    assert len(vector1) == 1024
    assert len(vector3) == 1024

    # Test determinism
    assert vector1 == vector2
    assert vector1 != vector3

    # Test list embedding
    vectors = client.embed_texts([text1, text3])
    assert len(vectors) == 2
    assert vectors[0] == vector1
    assert vectors[1] == vector3


def test_agent_models_in_db():
    """Verify that we can write and read all four agent tables in the active
    database context.

    Self-contained: creates its own User/Cohort/Course chain rather than
    hardcoding course_id=1/learner_id=1, which silently assumed rows with
    those ids already existed in whatever DATABASE_URL points to and
    failed with a ForeignKeyViolation on any database that hasn't been
    seeded that way (e.g. a fresh local dev DB).

    All identifiers are unique per run so a leaked row from an aborted
    prior run can never collide with this one. Cleanup deletes course,
    then cohort, then user, committing after each: without an ORM
    relationship() connecting these models (they're plain foreign_key=
    columns), SQLAlchemy's unit-of-work has no way to infer delete order
    across them, so batching all three deletes into one flush can attempt
    to delete `user` before `course` and abort with a
    ForeignKeyViolation before the other deletes ever run. The entire
    setup/verify body lives inside the try so any failure -- not just an
    assertion failure -- still triggers cleanup.
    """
    run_id = uuid.uuid4().hex[:8]
    with Session(engine) as session:
        user = cohort = course = None
        try:
            user = User(
                email=f"test_agent_models_in_db_{run_id}@example.com",
                hashed_password="not-a-real-hash",
                role=UserRole.LEARNER,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

            cohort = Cohort(
                name=f"test_agent_models_in_db cohort {run_id}",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                created_by=user.id,
            )
            session.add(cohort)
            session.commit()
            session.refresh(cohort)

            course = Course(
                title=f"test_agent_models_in_db course {run_id}",
                cohort_id=cohort.id,
                created_by=user.id,
            )
            session.add(course)
            session.commit()
            session.refresh(course)

            # 1. ContentEmbedding
            emb = ContentEmbedding(
                course_id=course.id,
                module_id=None,
                content_type="faq",
                text="FAQ sample question and answer",
                embedding=[0.1] * 1024,
            )
            session.add(emb)

            # 2. Escalation
            esc = Escalation(
                learner_id=user.id,
                course_id=course.id,
                trainer_id=None,
                question="What is a variable?",
                reason=EscalationReason.MODEL_UNCERTAINTY,
                detail="Self-reported uncertainty",
                status="pending",
            )
            session.add(esc)

            # 3. ConversationHistory
            history = ConversationHistory(
                learner_id=user.id,
                course_id=course.id,
                module_id=None,
                role=ChatRole.USER,
                message="Hi there",
            )
            session.add(history)

            # 4. QueryLog
            log = QueryLog(
                learner_id=user.id,
                course_id=course.id,
                module_id=None,
                assignment_id=None,
                query_type=QueryType.CHAT.value,
                question="What is a loop?",
                retrieved_chunk_ids=["chunk_1", "chunk_2"],
                confidence_score=0.95,
                is_confident=True,
                escalated=False,
                escalation_reason=None,
                escalation_detail=None,
                escalation_id=None,
                latency_ms=120,
            )
            session.add(log)

            session.commit()

            # Retrieve and verify
            db_emb = session.exec(
                select(ContentEmbedding).where(ContentEmbedding.text == emb.text)
            ).first()
            assert db_emb is not None
            assert len(db_emb.embedding) == 1024
            assert db_emb.content_type == "faq"

            db_esc = session.exec(
                select(Escalation).where(Escalation.question == esc.question)
            ).first()
            assert db_esc is not None
            assert db_esc.reason == EscalationReason.MODEL_UNCERTAINTY
            assert db_esc.status == "pending"

            db_hist = session.exec(
                select(ConversationHistory).where(
                    ConversationHistory.message == history.message
                )
            ).first()
            assert db_hist is not None
            assert db_hist.role == ChatRole.USER

            db_log = session.exec(
                select(QueryLog).where(QueryLog.question == log.question)
            ).first()
            assert db_log is not None
            assert db_log.confidence_score == 0.95
            assert db_log.retrieved_chunk_ids == ["chunk_1", "chunk_2"]
            assert db_log.query_type == QueryType.CHAT.value
            assert db_log.is_confident is True
            assert db_log.latency_ms == 120

            # Clean up the agent-table rows before the outer finally
            # cleans up the User/Cohort/Course chain they depend on.
            session.delete(db_emb)
            session.delete(db_esc)
            session.delete(db_hist)
            session.delete(db_log)
            session.commit()
        finally:
            # Always clean up the seed chain, even on assertion failure,
            # so this test never leaves rows behind for the next run.
            # Deleted and committed one at a time, in FK-safe order
            # (course -> cohort -> user), for the reason explained above.
            if course is not None:
                session.delete(course)
                session.commit()
            if cohort is not None:
                session.delete(cohort)
                session.commit()
            if user is not None:
                session.delete(user)
                session.commit()