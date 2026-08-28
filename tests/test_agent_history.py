"""
Unit tests for conversation_history / query_logs read/write logic, against
an in-memory SQLite engine (no Postgres required).

Run with: pytest tests/test_agent_history.py -v
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.agent.graph.state import ChatRole, EscalationReason, QueryType
from app.agent.model import ConversationHistory, QueryLog
from app.agent.repository import (
    ConversationHistoryRepository,
    QueryLogRepository,
)
from app.agent.service import load_chat_history, record_interaction


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(
        engine, tables=[ConversationHistory.__table__, QueryLog.__table__]
    )
    with Session(engine) as s:
        yield s


def test_add_exchange_writes_both_turns_in_order(session):
    repo = ConversationHistoryRepository(session, learner_id=1)
    repo.add_exchange(
        course_id=101,
        module_id=1001,
        question="How does a for loop work?",
        final_response="It repeats a block of code.",
    )

    turns = repo.get_recent(course_id=101, limit=6)
    assert [t.role for t in turns] == [ChatRole.USER, ChatRole.ASSISTANT]
    assert turns[0].message == "How does a for loop work?"
    assert turns[1].message == "It repeats a block of code."


def test_get_recent_is_scoped_to_learner(session):
    repo1 = ConversationHistoryRepository(session, learner_id=1)
    repo2 = ConversationHistoryRepository(session, learner_id=2)

    repo1.add_exchange(
        course_id=101, module_id=None, question="q1", final_response="a1"
    )
    repo2.add_exchange(
        course_id=101, module_id=None, question="q2", final_response="a2"
    )

    assert len(repo1.get_recent(course_id=101, limit=10)) == 2
    assert len(repo2.get_recent(course_id=101, limit=10)) == 2
    assert repo1.get_recent(course_id=101, limit=10)[0].message == "q1"


def test_get_recent_respects_window_and_oldest_first_order(session):
    repo = ConversationHistoryRepository(session, learner_id=1)
    for i in range(5):
        repo.add_exchange(
            course_id=101,
            module_id=None,
            question=f"q{i}",
            final_response=f"a{i}",
        )

    windowed = repo.get_recent(course_id=101, limit=4)
    assert len(windowed) == 4
    # Oldest-first among the most recent 4 turns (a3, q4, a4 plus one more).
    assert windowed[-1].message == "a4"
    assert windowed[0].created_at <= windowed[-1].created_at


def test_load_chat_history_returns_chat_turn_shape(session):
    repo = ConversationHistoryRepository(session, learner_id=1)
    repo.add_exchange(
        course_id=101, module_id=None, question="q", final_response="a"
    )

    history = load_chat_history(
        repo, course_id=101, module_id=None, max_turns=6
    )
    assert history == [
        {"role": "user", "message": "q"},
        {"role": "assistant", "message": "a"},
    ]


def test_get_page_paginates_newest_first(session):
    repo = ConversationHistoryRepository(session, learner_id=1)
    for i in range(3):
        repo.add_exchange(
            course_id=101,
            module_id=None,
            question=f"q{i}",
            final_response=f"a{i}",
        )

    page, total = repo.get_page(course_id=101, limit=2, offset=0)
    assert total == 6
    assert len(page) == 2
    assert page[0].message == "a2"  # newest first


def test_record_interaction_writes_history_and_query_log(session):
    state = {
        "question": "How does a for loop work?",
        "final_response": "It repeats a block of code.",
        "query_type": QueryType.CHAT,
        "assignment_id": None,
        "retrieved_chunks": [
            {"chunk_id": "c1", "score": 0.91},
            {"chunk_id": "c2", "score": 0.4},
        ],
        "confidence_score": 0.91,
        "is_confident": True,
        "escalated": False,
        "escalation_reason": None,
        "escalation_detail": None,
        "escalation_id": None,
    }
    record_interaction(
        session,
        learner_id=1,
        course_id=101,
        module_id=1001,
        state=state,
        latency_ms=250,
    )

    history_repo = ConversationHistoryRepository(session, learner_id=1)
    assert len(history_repo.get_recent(course_id=101, limit=10)) == 2

    log = session.exec(select(QueryLog)).first()
    assert log is not None
    assert log.is_confident is True
    assert log.escalated is False
    assert log.top_retrieval_score == 0.91
    assert log.query_type == QueryType.CHAT.value
    assert log.retrieved_chunk_ids == ["c1", "c2"]
    assert log.latency_ms == 250


def test_record_interaction_stores_escalation_reason_as_string(session):
    state = {
        "question": "off-topic",
        "final_response": "passed to your trainer",
        "query_type": QueryType.CHAT,
        "assignment_id": None,
        "retrieved_chunks": [],
        "confidence_score": 0.0,
        "is_confident": False,
        "escalated": True,
        "escalation_reason": EscalationReason.NO_RELEVANT_CONTEXT,
        "escalation_detail": "no context",
        "escalation_id": 7,
    }
    record_interaction(
        session,
        learner_id=1,
        course_id=101,
        module_id=None,
        state=state,
        latency_ms=90,
    )

    log = session.exec(select(QueryLog)).first()
    assert log.escalation_reason == "no_relevant_context"
    assert log.escalation_id == 7


def test_query_log_repository_record_persists_row(session):
    repo = QueryLogRepository(session)
    log = repo.record(
        learner_id=1,
        course_id=101,
        module_id=None,
        assignment_id=None,
        query_type=QueryType.CHAT.value,
        question="q",
        retrieved_chunk_ids=["c1"],
        top_retrieval_score=0.7,
        confidence_score=0.7,
        is_confident=True,
        escalated=False,
        escalation_reason=None,
        escalation_detail=None,
        escalation_id=None,
        latency_ms=110,
    )
    assert log.id is not None
    assert log.retrieved_chunk_ids == ["c1"]
    assert log.latency_ms == 110