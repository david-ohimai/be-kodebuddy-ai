"""
Tests for Dev B's retrieval layer.

Owner: Dev B (Retrieval & Tools)

Two groups:

* Unit tests — no database, no network. They cover the logic this layer owns
  outright: brief formatting, escalation validation, blank-query handling, and
  the embedding seam.
* Integration tests — marked `postgres`, skipped unless `TEST_DATABASE_URL` is
  set. The RBAC test lives here because the guarantee being tested is enforced
  by the SQL itself; asserting it against a mock would only test the mock.

Run the unit tests with:      pytest tests/test_agent_retrieval.py
Include the integration set:  TEST_DATABASE_URL=postgresql+psycopg://... pytest
"""

from __future__ import annotations

import datetime as dt
import os

import pytest

from app.agent.embedding_seam import embed_query, reset_embedder_cache
from app.agent.repository import AgentRepository
from app.agent.tools.escalate_to_trainer import make_escalate_to_trainer
from app.agent.tools.search_curriculum import make_search_curriculum
from app.agent.types import (
    AssignmentBrief,
    EmbeddingUnavailableError,
    EscalationReason,
    EscalationWriteError,
)


@pytest.fixture(autouse=True)
def _stub_embeddings(monkeypatch):
    """Use deterministic stub vectors; Dev A's provider is not under test."""
    monkeypatch.setenv("AGENT_FAKE_EMBEDDINGS", "1")
    reset_embedder_cache()
    yield
    reset_embedder_cache()


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row


class _FakeSession:
    """Minimal stand-in that returns one prepared row from `execute`."""

    def __init__(self, row):
        self._row = row

    def execute(self, statement, params=None):
        return _FakeResult(self._row)

    def rollback(self):  # pragma: no cover - not exercised here
        pass


def _row(**overrides) -> dict:
    """
    A row shaped like the assignment lookup's SELECT.

    Types mirror the real columns: `assignments.due_date` is a DATETIME and
    `assignments.maximum_score` is a FLOAT.
    """
    base = {
        "assignment_id": 2,
        "course_id": 1,
        "module_id": 3,
        "title": "Build a FastAPI CRUD router",
        "description": "Implement create, read, update and delete endpoints.",
        "due_date": dt.datetime(2026, 9, 1, 23, 59, tzinfo=dt.timezone.utc),
        "maximum_score": 100.0,
    }
    base.update(overrides)
    return base


def test_assignment_brief_reduces_a_datetime_due_date_to_an_iso_date():
    """
    `assignments.due_date` is a DATETIME, but Dev C's prompt renders the value
    verbatim as "Due: {due_date}". Passing the full timestamp through would put
    "2026-09-01T23:59:00+00:00" in front of the model instead of a plain date.
    """
    repository = AgentRepository(session=_FakeSession(_row()), learner_id=4)  # type: ignore[arg-type]

    brief = repository.get_assignment(2)

    assert brief is not None
    assert brief["due_date"] == "2026-09-01"
    assert isinstance(brief["due_date"], str)


def test_assignment_brief_narrows_an_integral_float_score_to_int():
    repository = AgentRepository(session=_FakeSession(_row()), learner_id=4)  # type: ignore[arg-type]

    brief = repository.get_assignment(2)

    assert brief["maximum_score"] == 100
    assert isinstance(brief["maximum_score"], int)


def test_assignment_brief_never_truncates_a_fractional_score():
    """
    `maximum_score` is a FLOAT column. int() would turn 92.5 into 92 and show
    the learner a maximum that does not exist.
    """
    repository = AgentRepository(  # type: ignore[arg-type]
        session=_FakeSession(_row(maximum_score=92.5)), learner_id=4
    )

    assert repository.get_assignment(2)["maximum_score"] == 92.5


def test_assignment_brief_passes_through_an_already_string_due_date():
    repository = AgentRepository(  # type: ignore[arg-type]
        session=_FakeSession(_row(due_date="2026-09-01")), learner_id=4
    )

    assert repository.get_assignment(2)["due_date"] == "2026-09-01"


def test_assignment_brief_coerces_a_null_description_to_empty_string():
    """
    prompts/assignment_guidance.py joins description straight into the prompt,
    so a NULL would raise a TypeError mid-render rather than degrade.
    """
    repository = AgentRepository(  # type: ignore[arg-type]
        session=_FakeSession(_row(description=None)), learner_id=4
    )

    brief = repository.get_assignment(2)

    assert brief["description"] == ""
    assert "\n".join([brief["title"], "", brief["description"]])  # must not raise


def test_assignment_brief_keeps_optional_score_nullable():
    repository = AgentRepository(  # type: ignore[arg-type]
        session=_FakeSession(_row(due_date=None, maximum_score=None)),
        learner_id=4,
    )

    brief = repository.get_assignment(2)

    assert brief["due_date"] is None
    assert brief["maximum_score"] is None


def test_escalation_rejects_a_learner_id_mismatch():
    """
    An escalation attributed to the wrong learner sends a trainer to the wrong
    person, so the bound learner wins over the passed argument.
    """
    repository = AgentRepository(session=None, learner_id=4)  # type: ignore[arg-type]
    escalate = make_escalate_to_trainer(repository)

    with pytest.raises(EscalationWriteError, match="does not match"):
        escalate(
            learner_id=99,
            course_id=1,
            trainer_id=7,
            question="How do I submit?",
            reason=EscalationReason.NO_RELEVANT_CONTEXT,
        )


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_escalation_rejects_a_blank_question(blank):
    repository = AgentRepository(session=None, learner_id=4)  # type: ignore[arg-type]
    escalate = make_escalate_to_trainer(repository)

    with pytest.raises(EscalationWriteError):
        escalate(
            learner_id=4,
            course_id=1,
            trainer_id=7,
            question=blank,
            reason=EscalationReason.NO_RELEVANT_CONTEXT,
        )


def test_escalation_requires_a_reason():
    repository = AgentRepository(session=None, learner_id=4)  # type: ignore[arg-type]
    escalate = make_escalate_to_trainer(repository)

    with pytest.raises(EscalationWriteError, match="requires a reason"):
        escalate(
            learner_id=4,
            course_id=1,
            trainer_id=7,
            question="a real question",
            reason=None,  # type: ignore[arg-type]
        )


def test_blank_query_returns_no_chunks_without_touching_the_database():
    """A blank query short-circuits before the session is ever used."""
    repository = AgentRepository(session=None, learner_id=4)  # type: ignore[arg-type]
    search = make_search_curriculum(repository)

    assert search(query="", course_id=1) == []
    assert search(query="   ", course_id=1) == []


def test_embedding_seam_is_deterministic_and_normalised():
    first = list(embed_query("how do I structure a FastAPI project"))
    second = list(embed_query("how do I structure a FastAPI project"))

    assert first == second
    assert first != list(embed_query("something else entirely"))
    assert abs(sum(value * value for value in first) ** 0.5 - 1.0) < 1e-9


def test_embedding_seam_rejects_a_blank_query():
    with pytest.raises(EmbeddingUnavailableError):
        embed_query("   ")


def test_repository_requires_a_learner_id():
    with pytest.raises(ValueError, match="learner_id is required"):
        AgentRepository(session=None, learner_id=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Integration tests (Postgres + pgvector)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

postgres = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set TEST_DATABASE_URL to run the RBAC integration tests.",
)


@pytest.fixture
def session():
    from sqlmodel import Session, create_engine

    engine = create_engine(TEST_DATABASE_URL)
    with Session(engine) as active_session:
        yield active_session


@postgres
def test_enrolled_learner_sees_only_their_own_courses(session):
    """
    The core guarantee: scoping is enforced by the query, so a learner asking
    about a course they are not assigned to gets nothing back — regardless of
    what course_id the caller passes.

    Expects seed data: a learner enrolled in exactly one course, and at least
    one other course with embedded content that they are NOT enrolled in.
    Populate via the /courses/{id}/assign-learner endpoint.
    """
    learner_id = int(os.environ["TEST_LEARNER_ID"])
    unenrolled_course_id = int(os.environ["TEST_UNENROLLED_COURSE_ID"])

    repository = AgentRepository(session=session, learner_id=learner_id)
    enrolled = repository.enrolled_course_ids()

    assert unenrolled_course_id not in enrolled, "Test fixture is wrong."
    assert repository.is_enrolled(unenrolled_course_id) is False

    search = make_search_curriculum(repository)
    chunks = search(query="anything at all", course_id=unenrolled_course_id)

    assert chunks == [], "RBAC leak: content returned for an unenrolled course."


@postgres
def test_unscoped_search_never_leaves_the_learners_courses(session):
    """
    Omitting course_id widens the search, but never widens access.

    `None` is permitted in the result set: that is global FAQ content, which
    belongs to no course and is readable by any learner. Every non-global
    chunk must still come from a course this learner is enrolled in.
    """
    learner_id = int(os.environ["TEST_LEARNER_ID"])

    repository = AgentRepository(session=session, learner_id=learner_id)
    enrolled = set(repository.enrolled_course_ids())

    chunks = repository.search_content(
        query_embedding=embed_query("anything at all"), limit=50
    )

    assert {chunk["course_id"] for chunk in chunks} <= enrolled | {None}

    for chunk in chunks:
        if chunk["course_id"] is None:
            assert chunk["content_type"] == "faq", (
                "Only FAQ content may be global; "
                f"got a global {chunk['content_type']} chunk."
            )


@postgres
def test_global_faqs_are_visible_without_course_enrollment(session):
    """
    The MVP FAQ set is global (course_id NULL). Those rows must be reachable
    by any enrolled learner, in any course context.

    Expects at least one ingested FAQ chunk with course_id NULL.
    """
    learner_id = int(os.environ["TEST_LEARNER_ID"])
    repository = AgentRepository(session=session, learner_id=learner_id)

    chunks = repository.search_content(
        query_embedding=embed_query("How do I submit an assignment?"),
        content_type="faq",
        limit=50,
    )

    assert any(chunk["course_id"] is None for chunk in chunks), (
        "No global FAQ content reachable — check that ingestion wrote "
        "course_id NULL rows and that the column is nullable."
    )


@postgres
def test_global_visibility_is_limited_to_faq_content(session):
    """
    A NULL course_id must NOT make curriculum or resource content universally
    visible. Those rows fail closed: unreachable rather than unscoped.
    """
    learner_id = int(os.environ["TEST_LEARNER_ID"])
    repository = AgentRepository(session=session, learner_id=learner_id)
    enrolled = set(repository.enrolled_course_ids())

    for content_type in ("curriculum", "resource"):
        chunks = repository.search_content(
            query_embedding=embed_query("anything at all"),
            content_type=content_type,
            limit=50,
        )
        assert all(chunk["course_id"] in enrolled for chunk in chunks), (
            f"{content_type} content leaked with a NULL or unenrolled course_id."
        )


@postgres
def test_assignment_brief_is_hidden_from_an_unenrolled_learner(session):
    """
    An assignment in a course the learner is not enrolled in must be
    indistinguishable from one that does not exist.
    """
    from app.agent.tools.get_assignment_brief import make_get_assignment_brief

    learner_id = int(os.environ["TEST_LEARNER_ID"])
    foreign_assignment_id = int(os.environ["TEST_FOREIGN_ASSIGNMENT_ID"])

    repository = AgentRepository(session=session, learner_id=learner_id)
    get_brief = make_get_assignment_brief(repository)

    assert get_brief(foreign_assignment_id) is None
    assert get_brief(10**9) is None  # nonexistent id looks identical
