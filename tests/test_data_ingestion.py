from sqlmodel import Session, select
from app.core.database import engine
from app.agent.embeddings import EmbeddingsClient
from app.agent.model import ContentEmbedding, Escalation, ConversationHistory, QueryLog
from app.agent.graph.state import EscalationReason


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
    database context."""
    with Session(engine) as session:
        # 1. ContentEmbedding
        emb = ContentEmbedding(
            course_id=1,
            module_id=None,
            content_type="faq",
            text="FAQ sample question and answer",
            embedding=[0.1] * 1024,
        )
        session.add(emb)

        # 2. Escalation
        esc = Escalation(
            learner_id=1,
            course_id=1,
            trainer_id=None,
            question="What is a variable?",
            reason=EscalationReason.MODEL_UNCERTAINTY,
            detail="Self-reported uncertainty",
            status="pending",
        )
        session.add(esc)

        # 3. ConversationHistory
        history = ConversationHistory(
            learner_id=1,
            course_id=1,
            role="user",
            message="Hi there",
        )
        session.add(history)

        # 4. QueryLog
        log = QueryLog(
            learner_id=1,
            course_id=1,
            question="What is a loop?",
            retrieved_chunk_ids=["chunk_1", "chunk_2"],
            confidence_score=0.95,
            escalated=False,
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
            select(ConversationHistory).where(ConversationHistory.message == history.message)
        ).first()
        assert db_hist is not None
        assert db_hist.role == "user"

        db_log = session.exec(
            select(QueryLog).where(QueryLog.question == log.question)
        ).first()
        assert db_log is not None
        assert db_log.confidence_score == 0.95
        assert db_log.retrieved_chunk_ids == ["chunk_1", "chunk_2"]

        # Clean up test insertions
        session.delete(db_emb)
        session.delete(db_esc)
        session.delete(db_hist)
        session.delete(db_log)
        session.commit()
