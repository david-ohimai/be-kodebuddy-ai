"""
Data access for the agent: scoped vector search, assignment lookup,
escalation writes, conversation-history read/write, and query_logs writes.

Owners: Dev B (AgentRepository -- retrieval, assignments, escalations) and
Dev E (ConversationHistoryRepository, QueryLogRepository -- history &
observability). Merged into one module so callers have a single import
site for every table this feature touches, after the split across
repository.py / history_repository.py caused service.py and router.py to
import ConversationHistoryRepository/QueryLogRepository from the wrong
module (repository.py instead of history_repository.py), breaking app
startup.

RBAC IS ENFORCED IN THE SQL, NOT ABOVE IT
-----------------------------------------
Every read in this module joins `course_learners` on the learner's own id. A
learner who is not enrolled in a course gets zero rows for that course no
matter what `course_id` is passed in, so there is no code path — including a
buggy caller, or a caller that forgets to check — that can surface content from
a course the learner is not assigned to. This is the guarantee the design
document calls out as non-negotiable, and it is the reason the tools are bound
to a learner at construction time rather than taking `learner_id` as an
argument they could be handed the wrong value for.

TABLES OWNED BY OTHERS
----------------------
`content_embeddings` and `escalations` belong to Dev A's `app/agent/model.py`.
AgentRepository below still accesses them through parameterised raw SQL rather
than an ORM import -- that choice predates model.py landing and is kept as-is
here (not revisited as part of this merge); ConversationHistoryRepository and
QueryLogRepository, merged in below from the old history_repository.py, do
use the ORM directly against model.py, since Dev E always had it available.
The column contract for the raw-SQL tables is documented below; if the real
schema differs, the constants at the top of this file are the only thing
that needs to change.

    content_embeddings
        id            integer primary key
        course_id     integer NULL      -> courses.id   (see below)
        module_id     integer null      -> modules.id
        content_type  text not null     -- 'curriculum' | 'faq' | 'resource'
        chunk_text    text not null
        embedding     vector(N) not null

    DECIDED: FAQs are global (Option A, resolved 2026-08-25). `course_id` is
    nullable on this table as of migration f3a9c1d84b2e. A FAQ chunk with
    course_id NULL is visible to every enrolled learner; a FAQ chunk with a
    real course_id is scoped to that course only, same as curriculum content.
    Curriculum and resource rows should always carry a real course_id —
    that's enforced in scripts/ingest_curriculum.py, not the database schema.

    Global rows are readable by any authenticated learner, so the search query
    permits a NULL course_id ONLY for content_type 'faq'. A NULL course_id on
    curriculum or resource content is unreachable rather than universally
    visible — a mis-ingested row fails closed, not open.

    escalations
        id                integer primary key
        learner_id        integer not null  -> users.id
        course_id         integer not null  -> courses.id
        module_id         integer null      -> modules.id
        assignment_id     integer null      -> assignments.id
        trainer_id        integer null      -> users.id
        question          text not null
        reason            text not null     -- an EscalationReason value
        detail            text null         -- free-form context for the reason
        draft_response    text null         -- agent's own best-effort answer, if any/safe
        confidence_score  float null        -- graph's confidence_score for that draft
        status            text not null     -- 'open' on insert
        created_at        timestamptz not null

    NOTE FOR DEV A: `trainer_id` and `detail` are additions since the first
    draft of this contract, and come from Dev C's `EscalateToTrainerFn` in
    graph/contracts.py — the graph resolves a trainer upstream and passes a
    structured `EscalationReason` plus free-form `detail`. `trainer_id` must be
    NULLABLE: the graph deliberately escalates even when that lookup failed,
    rather than dropping the learner's question, and those rows are the
    unassigned-escalations queue.

    NOTE: `module_id`, `assignment_id`, `draft_response`, `confidence_score`
    (migration a1c2e3f4b5d6) are later additions, added once it became clear
    a trainer looking at an escalation with only `question`/`reason` had no
    way to tell what the agent actually attempted or which part of the
    course it came from. All four are nullable and populated from whatever
    the frontend already had on the originating chat turn -- no learner
    ever re-types this data.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlmodel import Session, func, select

from app.agent.embedding_seam import to_pgvector_literal
from app.agent.graph.state import ChatRole
from app.agent.model import ConversationHistory, QueryLog
from app.agent.types import (
    FAQ,
    AssignmentBrief,
    ContentStoreUnavailableError,
    ContentType,
    EscalationReason,
    EscalationWriteError,
    RetrievedChunk,
)

logger = logging.getLogger(__name__)

# --- Dev A's schema contract (see module docstring) ------------------------
EMBEDDINGS_TABLE = "content_embeddings"
EMBEDDINGS_TEXT_COLUMN = "text"
EMBEDDINGS_VECTOR_COLUMN = "embedding"
ESCALATIONS_TABLE = "escalations"

# Default number of chunks returned by a similarity search.
DEFAULT_SEARCH_LIMIT = 5

# Hard ceiling, so a caller cannot ask for an unbounded result set.
MAX_SEARCH_LIMIT = 50

# Status assigned to a newly created escalation.
ESCALATION_STATUS_OPEN = "open"


def _is_missing_relation(exc: ProgrammingError) -> bool:
    """
    True when a ProgrammingError is Postgres complaining that a relation or
    type does not exist — i.e. Dev A's migration has not been applied.

    Matched on the SQLSTATE code where psycopg exposes one (42P01 undefined
    table, 42704 undefined object, 42883 undefined function — the last covers
    a missing pgvector `<=>` operator), and on the message text otherwise.
    """
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    if sqlstate in {"42P01", "42704", "42883"}:
        return True
    message = str(exc).lower()
    return "does not exist" in message and (
        EMBEDDINGS_TABLE in message
        or ESCALATIONS_TABLE in message
        or "vector" in message
    )


class AgentRepository:
    """
    Database access for the agent, scoped to a single learner.

    The learner id is supplied once, at construction, and every query in this
    class filters on it. Constructing one of these per request is the intended
    usage — see `app.agent.tools.factory.AgentTools`.
    """

    def __init__(self, session: Session, learner_id: int) -> None:
        if learner_id is None:
            raise ValueError("learner_id is required — RBAC cannot be skipped.")
        self.session = session
        self.learner_id = int(learner_id)

    # ------------------------------------------------------------------
    # Enrollment
    # ------------------------------------------------------------------

    def is_enrolled(self, course_id: int) -> bool:
        """
        Whether this learner is assigned to an active course.

        Uses direct course assignment (`course_learners`) as the authority,
        which is what the design document means by "courses they're actually
        assigned to". Cohort membership is deliberately *not* treated as
        implying course access — see the note in `enrolled_course_ids`.
        """
        statement = text(
            """
            SELECT 1
            FROM course_learners cl
            JOIN courses c ON c.id = cl.course_id
            WHERE cl.learner_id = CAST(:learner_id AS INTEGER)
              AND cl.course_id = CAST(:course_id AS INTEGER)
              AND c.is_active IS TRUE
            LIMIT 1
            """
        )
        row = self.session.execute(
            statement,
            {"learner_id": self.learner_id, "course_id": int(course_id)},
        ).first()
        return row is not None

    def enrolled_course_ids(self) -> list[int]:
        """
        Every active course this learner is assigned to.

        NOTE FOR REVIEW: `cohort_learners` also exists and carries an
        `is_active` flag. We do not consult it here, because a learner in a
        cohort is not necessarily assigned every course in that cohort —
        `course_learners` is the explicit grant. If the team decides cohort
        membership should also confer access, this is the single method to
        change; every read below derives its scope from the same join.
        """
        statement = text(
            """
            SELECT cl.course_id
            FROM course_learners cl
            JOIN courses c ON c.id = cl.course_id
            WHERE cl.learner_id = CAST(:learner_id AS INTEGER)
              AND c.is_active IS TRUE
            ORDER BY cl.course_id
            """
        )
        rows = self.session.execute(
            statement, {"learner_id": self.learner_id}
        ).all()
        return [int(row[0]) for row in rows]

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    def search_content(
        self,
        *,
        query_embedding: Sequence[float],
        course_id: int | None = None,
        module_id: int | None = None,
        content_type: ContentType | Sequence[ContentType] | None = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        """
        Similarity search over embedded content, scoped to this learner.

        The `course_learners` join is the access control. Passing a
        `course_id` the learner is not enrolled in yields an empty list rather
        than an error, so callers cannot probe for the existence of content in
        other courses.

        Args:
            query_embedding: the embedded search query.
            course_id: restrict to one course. When None, searches every course
                the learner is enrolled in.
            module_id: restrict to one module within the course.
            content_type: 'curriculum', 'faq', or 'resource' — a single value,
                a sequence of values (e.g. search curriculum *and* resource
                content in one call), or None to search every content type.
            limit: maximum chunks to return (clamped to MAX_SEARCH_LIMIT).
            min_score: drop chunks whose cosine similarity is below this.

        Raises:
            ContentStoreUnavailableError: the embeddings table or the pgvector
                extension is not present.
        """
        if not query_embedding:
            raise ValueError("query_embedding must be a non-empty vector.")

        effective_limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))

        content_types: list[str] | None
        if content_type is None:
            content_types = None
        elif isinstance(content_type, str):
            content_types = [content_type]
        else:
            content_types = list(content_type)

        statement = text(
            f"""
            SELECT
                ce.id                                   AS chunk_id,
                ce.course_id                            AS course_id,
                ce.module_id                            AS module_id,
                ce.content_type                         AS content_type,
                ce.{EMBEDDINGS_TEXT_COLUMN}             AS text,
                1 - (ce.{EMBEDDINGS_VECTOR_COLUMN} <=> CAST(:query_embedding AS vector))
                                                        AS score
            FROM {EMBEDDINGS_TABLE} ce
            WHERE (
                    -- Global content: belongs to no single course. ONLY FAQ
                    -- content may be global (see module docstring); a NULL
                    -- course_id on any other content type is unreachable
                    -- rather than universally visible, so a bad ingestion
                    -- row fails closed.
                    (ce.course_id IS NULL
                     AND ce.content_type = CAST(:global_content_type AS TEXT))
                    OR EXISTS (
                        SELECT 1
                        FROM course_learners cl
                        JOIN courses c ON c.id = cl.course_id
                        WHERE cl.course_id = ce.course_id
                          AND cl.learner_id = CAST(:learner_id AS INTEGER)
                          AND c.is_active IS TRUE
                    )
                  )
              AND (CAST(:course_id AS INTEGER) IS NULL
                   OR ce.course_id = CAST(:course_id AS INTEGER)
                   OR ce.course_id IS NULL)
              AND (CAST(:module_id AS INTEGER) IS NULL
                   OR ce.module_id = CAST(:module_id AS INTEGER))
              -- Content in a deactivated module must stop grounding answers.
              -- module_id is NULL for global FAQ content, which has no module.
              AND (ce.module_id IS NULL
                   OR EXISTS (
                        SELECT 1
                        FROM modules m
                        WHERE m.id = ce.module_id
                          AND m.is_active IS TRUE
                   ))
              AND (CAST(:content_types AS TEXT[]) IS NULL
                   OR ce.content_type = ANY(CAST(:content_types AS TEXT[])))
              AND (CAST(:min_score AS FLOAT) IS NULL
                   OR 1 - (ce.{EMBEDDINGS_VECTOR_COLUMN}
                           <=> CAST(:query_embedding AS vector))
                      >= CAST(:min_score AS FLOAT))
            ORDER BY ce.{EMBEDDINGS_VECTOR_COLUMN} <=> CAST(:query_embedding AS vector)
            LIMIT :limit
            """
        )

        params: dict[str, Any] = {
            "query_embedding": to_pgvector_literal(query_embedding),
            "learner_id": self.learner_id,
            "course_id": int(course_id) if course_id is not None else None,
            "module_id": int(module_id) if module_id is not None else None,
            "content_types": content_types,
            "global_content_type": FAQ,
            "min_score": float(min_score) if min_score is not None else None,
            "limit": effective_limit,
        }

        try:
            rows = self.session.execute(statement, params).mappings().all()
        except ProgrammingError as exc:
            self.session.rollback()
            if _is_missing_relation(exc):
                raise ContentStoreUnavailableError(
                    f"'{EMBEDDINGS_TABLE}' or the pgvector extension is not "
                    "available. This table is owned by Dev A (Data & "
                    "Ingestion); apply that migration before using retrieval."
                ) from exc
            raise

        chunks: list[RetrievedChunk] = [
            {
                "chunk_id": str(row["chunk_id"]),
                "course_id": (
                    int(row["course_id"]) if row["course_id"] is not None else None
                ),
                "module_id": (
                    int(row["module_id"]) if row["module_id"] is not None else None
                ),
                "content_type": str(row["content_type"]),
                "text": row["text"],
                "score": float(row["score"]),
            }
            for row in rows
        ]

        logger.debug(
            "search_content learner=%s course=%s module=%s type=%s -> %d chunks",
            self.learner_id,
            course_id,
            module_id,
            content_type,
            len(chunks),
        )
        return chunks

    # ------------------------------------------------------------------
    # Assignments
    # ------------------------------------------------------------------

    def get_assignment(self, assignment_id: int) -> AssignmentBrief | None:
        """
        Fetch one assignment, if this learner is entitled to see it.

        Assignments hang off a module, and the module carries the course, so
        entitlement is `assignment -> module -> course -> course_learners`.

        Returns None both when the assignment does not exist and when the
        learner is not entitled to it. The two are deliberately
        indistinguishable to the caller so an unauthorised learner cannot use
        this to discover which assignment ids are real; the distinction is
        logged server-side instead.
        """
        statement = text(
            """
            SELECT
                a.id            AS assignment_id,
                m.course_id     AS course_id,
                a.module_id     AS module_id,
                a.title         AS title,
                a.description   AS description,
                a.due_date      AS due_date,
                a.maximum_score AS maximum_score
            FROM assignments a
            JOIN modules m
              ON m.id = a.module_id
            JOIN courses c
              ON c.id = m.course_id
            JOIN course_learners cl
              ON cl.course_id = m.course_id
             AND cl.learner_id = CAST(:learner_id AS INTEGER)
            WHERE a.id = CAST(:assignment_id AS INTEGER)
              AND a.is_active IS TRUE
              AND m.is_active IS TRUE
              AND c.is_active IS TRUE
            LIMIT 1
            """
        )

        try:
            row = (
                self.session.execute(
                    statement,
                    {
                        "learner_id": self.learner_id,
                        "assignment_id": int(assignment_id),
                    },
                )
                .mappings()
                .first()
            )
        except ProgrammingError as exc:
            self.session.rollback()
            if _is_missing_relation(exc):
                logger.warning(
                    "Assignment lookup skipped — a required table is missing: %s",
                    exc,
                )
                return None
            raise

        if row is None:
            logger.info(
                "No assignment brief for assignment_id=%s learner_id=%s "
                "(absent, inactive, or learner not enrolled).",
                assignment_id,
                self.learner_id,
            )
            return None

        description = row["description"]
        if description is None:
            logger.warning(
                "Assignment %s has no description; sending an empty brief body.",
                row["assignment_id"],
            )
            description = ""
        due_date = row["due_date"]
        if due_date is not None and not isinstance(due_date, str):
            if hasattr(due_date, "date"):  # datetime -> date
                due_date = due_date.date()
            due_date = due_date.isoformat()
        maximum_score = row["maximum_score"]
        if maximum_score is not None:
            maximum_score = float(maximum_score)
            if maximum_score.is_integer():
                maximum_score = int(maximum_score)

        return {
            "assignment_id": int(row["assignment_id"]),
            "course_id": int(row["course_id"]),
            "module_id": int(row["module_id"]),
            "title": row["title"],
            "description": description,
            "due_date": due_date,
            "maximum_score": maximum_score,
        }

    # ------------------------------------------------------------------
    # Escalations
    # ------------------------------------------------------------------

    def create_escalation(
        self,
        *,
        course_id: int,
        question: str,
        reason: EscalationReason,
        trainer_id: int | None = None,
        module_id: int | None = None,
        assignment_id: int | None = None,
        detail: str | None = None,
        draft_response: str | None = None,
        confidence_score: float | None = None,
    ) -> int:
        """
        Persist an escalation for the trainer dashboard and return its id.

        Committed immediately: an escalation is the record that a learner asked
        something the agent could not answer, and it must survive even if the
        rest of the request subsequently fails.

        Args:
            course_id: the course the question was asked against.
            question: the learner's original question, stored verbatim.
            reason: structured category, so escalations can be aggregated
                without parsing prose.
            trainer_id: resolved upstream by Dev D. None is valid and lands the
                row in the unassigned queue — never a reason to refuse the
                write, since a dropped escalation strands the learner.
            module_id: the module the question was asked in, if any --
                round-tripped from the originating chat turn so the trainer
                can jump straight to the relevant content instead of only
                knowing the course.
            assignment_id: the assignment the question was asked about, if
                any -- same rationale as module_id, populated only for
                ASSIGNMENT_GUIDANCE turns.
            detail: free-form context for the reason (e.g. the top score).
            draft_response: the agent's own best-effort answer, if it had
                one and it was safe to surface (never populated for a
                POLICY_VIOLATION reason -- see
                app/agent/graph/nodes.py::route). Gives the trainer
                something concrete to react to, not just a bare question.
            confidence_score: the graph's confidence_score (0.0-1.0) for
                that draft, if any.

        Raises:
            EscalationWriteError: if the row could not be written.
        """
        if not question or not question.strip():
            raise EscalationWriteError("Cannot escalate an empty question.")
        if reason is None:
            raise EscalationWriteError("An escalation requires a reason.")

        reason_value = (
            reason.value if isinstance(reason, EscalationReason) else str(reason)
        )
        if not reason_value.strip():
            raise EscalationWriteError("An escalation requires a reason.")

        statement = text(
            f"""
            INSERT INTO {ESCALATIONS_TABLE}
                (learner_id, course_id, module_id, assignment_id, trainer_id,
                 question, reason, detail, draft_response, confidence_score,
                 status, created_at, updated_at)
            VALUES
                (CAST(:learner_id AS INTEGER),
                 CAST(:course_id AS INTEGER),
                 CAST(:module_id AS INTEGER),
                 CAST(:assignment_id AS INTEGER),
                 CAST(:trainer_id AS INTEGER),
                 :question,
                 CAST(:reason AS escalationreason),
                 :detail,
                 :draft_response,
                 CAST(:confidence_score AS FLOAT),
                 :status,
                 NOW(), NOW())
            RETURNING id
            """
        )

        try:
            row = self.session.execute(
                statement,
                {
                    "learner_id": self.learner_id,
                    "course_id": int(course_id),
                    "module_id": (
                        int(module_id) if module_id is not None else None
                    ),
                    "assignment_id": (
                        int(assignment_id) if assignment_id is not None else None
                    ),
                    "trainer_id": (
                        int(trainer_id) if trainer_id is not None else None
                    ),
                    "question": question.strip(),
                    "reason": reason_value,
                    "detail": detail.strip() if detail else None,
                    "draft_response": (
                        draft_response.strip() if draft_response else None
                    ),
                    "confidence_score": (
                        float(confidence_score)
                        if confidence_score is not None
                        else None
                    ),
                    "status": ESCALATION_STATUS_OPEN,
                },
            ).first()
            if row is None:
                raise EscalationWriteError(
                    "Escalation insert returned no id."
                )
            self.session.commit()
        except ProgrammingError as exc:
            self.session.rollback()
            if _is_missing_relation(exc):
                raise EscalationWriteError(
                    f"'{ESCALATIONS_TABLE}' does not exist. This table is "
                    "owned by Dev A (Data & Ingestion); apply that migration "
                    "before escalation can be recorded."
                ) from exc
            raise EscalationWriteError(f"Could not write escalation: {exc}") from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise EscalationWriteError(f"Could not write escalation: {exc}") from exc

        escalation_id = int(row[0])
        logger.info(
            "Escalation %s created for learner=%s course=%s module=%s "
            "assignment=%s trainer=%s reason=%s",
            escalation_id,
            self.learner_id,
            course_id,
            module_id if module_id is not None else "n/a",
            assignment_id if assignment_id is not None else "n/a",
            trainer_id if trainer_id is not None else "unassigned",
            reason_value,
        )
        return escalation_id


# ----------------------------------------------------------------------
# Conversation history & query logs (formerly app/agent/history_repository.py)
# Owner: Dev E (History, Observability & Evals)
# ----------------------------------------------------------------------

class ConversationHistoryRepository:
    """
    Read/write access to `conversation_history`.

    Scoped to a single learner at construction time, matching the RBAC
    pattern in app/agent/repository.py (Dev B): a caller physically cannot
    read or write another learner's history through this class.
    """

    def __init__(self, session: Session, learner_id: int) -> None:
        self.session = session
        self.learner_id = int(learner_id)

    def add_turn(
        self,
        *,
        course_id: int,
        module_id: int | None,
        role: ChatRole,
        message: str,
    ) -> ConversationHistory:
        turn = ConversationHistory(
            learner_id=self.learner_id,
            course_id=course_id,
            module_id=module_id,
            role=role,
            message=message,
        )
        self.session.add(turn)
        self.session.commit()
        self.session.refresh(turn)
        return turn

    def add_exchange(
        self,
        *,
        course_id: int,
        module_id: int | None,
        question: str,
        final_response: str,
    ) -> None:
        """Convenience wrapper: writes the learner's question and the
        agent's final_response as two turns in one call, which is the
        common case after a single graph.invoke()."""
        self.session.add(
            ConversationHistory(
                learner_id=self.learner_id,
                course_id=course_id,
                module_id=module_id,
                role=ChatRole.USER,
                message=question,
            )
        )
        self.session.add(
            ConversationHistory(
                learner_id=self.learner_id,
                course_id=course_id,
                module_id=module_id,
                role=ChatRole.ASSISTANT,
                message=final_response,
            )
        )
        self.session.commit()

    def get_recent(
        self,
        *,
        course_id: int,
        module_id: int | None = None,
        limit: int = 6,
    ) -> list[ConversationHistory]:
        """
        Returns the most recent `limit` turns, oldest first — the order the
        graph's prompt builders expect (see graph/utils.py callers in
        nodes.py::reason).

        module_id is deliberately NOT filtered on: chat_history is meant to
        carry conversational context across a course, not just within one
        module, so a module-scoped question can still see a prior turn asked
        against a different module in the same course.
        """
        statement = (
            select(ConversationHistory)
            .where(ConversationHistory.learner_id == self.learner_id)
            .where(ConversationHistory.course_id == course_id)
            .order_by(ConversationHistory.created_at.desc())
            .limit(limit)
        )
        rows = list(self.session.exec(statement))
        return list(reversed(rows))

    def get_page(
        self,
        *,
        course_id: int | None = None,
        module_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ConversationHistory], int]:
        """Paginated, newest-first history for GET /agent/history."""
        base = select(ConversationHistory).where(
            ConversationHistory.learner_id == self.learner_id
        )
        if course_id is not None:
            base = base.where(ConversationHistory.course_id == course_id)
        if module_id is not None:
            base = base.where(ConversationHistory.module_id == module_id)

        total = self.session.exec(
            select(func.count()).select_from(base.subquery())
        ).one()

        rows = self.session.exec(
            base.order_by(ConversationHistory.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return list(rows), total


class QueryLogRepository:
    """Write-side access to `query_logs`. No RBAC scoping needed here — it's
    written internally by the agent service, never taken from a request."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        learner_id: int,
        course_id: int,
        module_id: int | None,
        assignment_id: int | None,
        query_type: str,
        question: str,
        retrieved_chunk_ids: list[str],
        top_retrieval_score: float | None,
        confidence_score: float,
        is_confident: bool,
        escalated: bool,
        escalation_reason: str | None,
        escalation_detail: str | None,
        escalation_id: int | None,
        latency_ms: int,
    ) -> QueryLog:
        log = QueryLog(
            learner_id=learner_id,
            course_id=course_id,
            module_id=module_id,
            assignment_id=assignment_id,
            query_type=query_type,
            question=question,
            retrieved_chunk_ids=retrieved_chunk_ids,
            top_retrieval_score=top_retrieval_score,
            confidence_score=confidence_score,
            is_confident=is_confident,
            escalated=escalated,
            escalation_reason=escalation_reason,
            escalation_detail=escalation_detail,
            escalation_id=escalation_id,
            latency_ms=latency_ms,
        )
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log