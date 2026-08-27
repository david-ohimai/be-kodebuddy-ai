"""
Data access for the agent: scoped vector search, assignment lookup, and
escalation writes.

Owner: Dev B (Retrieval & Tools)

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
`content_embeddings` and `escalations` belong to Dev A's `app/agent/model.py`,
which has not landed yet. They are accessed here through parameterised raw SQL
rather than an ORM import so this module stays importable and testable before
that file exists. The column contract is documented below; if Dev A's final
schema differs, the constants at the top of this file are the only thing that
needs to change.

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
        id          integer primary key
        learner_id  integer not null  -> users.id
        course_id   integer not null  -> courses.id
        trainer_id  integer null      -> users.id
        question    text not null
        reason      text not null     -- an EscalationReason value
        detail      text null         -- free-form context for the reason
        status      text not null     -- 'open' on insert
        created_at  timestamptz not null

    NOTE FOR DEV A: `trainer_id` and `detail` are additions since the first
    draft of this contract, and come from Dev C's `EscalateToTrainerFn` in
    graph/contracts.py — the graph resolves a trainer upstream and passes a
    structured `EscalationReason` plus free-form `detail`. `trainer_id` must be
    NULLABLE: the graph deliberately escalates even when that lookup failed,
    rather than dropping the learner's question, and those rows are the
    unassigned-escalations queue.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlmodel import Session

from app.agent.embedding_seam import to_pgvector_literal
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
        content_type: ContentType | None = None,
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
            content_type: 'curriculum', 'faq', or 'resource'.
            limit: maximum chunks to return (clamped to MAX_SEARCH_LIMIT).
            min_score: drop chunks whose cosine similarity is below this.

        Raises:
            ContentStoreUnavailableError: the embeddings table or the pgvector
                extension is not present.
        """
        if not query_embedding:
            raise ValueError("query_embedding must be a non-empty vector.")

        effective_limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))

        # `<=>` is pgvector's cosine *distance*; similarity is 1 - distance.
        # Ordering by the raw distance lets an ANN index be used if present.
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
              AND (CAST(:content_type AS TEXT) IS NULL
                   OR ce.content_type = CAST(:content_type AS TEXT))
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
            "content_type": content_type,
            "global_content_type": FAQ,
            "min_score": float(min_score) if min_score is not None else None,
            "limit": effective_limit,
        }

        try:
            rows = self.session.execute(statement, params).mappings().all()
        except ProgrammingError as exc:
            # A failed statement aborts the transaction; roll back so the
            # session stays usable for the caller's error handling.
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
                # None for global FAQ content, which belongs to no course.
                # NOTE: Dev C's RetrievedChunk types this as `int`; it needs
                # to become `int | None`, exactly as `module_id` already is.
                # Raised with Dev C — see the FAQ note in the module docstring.
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
                # assignments/modules are backend-team tables; treat a missing
                # one as "no brief available" so chat still works without them.
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

        # `description` is NOT NULL in Dev C's AssignmentBrief and is joined
        # straight into the prompt (prompts/assignment_guidance.py), so a NULL
        # from the DB would raise a TypeError mid-render. Ginikanwa's model
        # allows it to be null, so coerce here and say so in the log rather
        # than letting an incomplete assignment break guidance entirely.
        description = row["description"]
        if description is None:
            logger.warning(
                "Assignment %s has no description; sending an empty brief body.",
                row["assignment_id"],
            )
            description = ""

        # ISO 8601 *date* string, not a datetime: AssignmentBrief keeps itself
        # free of any datetime dependency so it serialises cleanly across a
        # process boundary, and Dev C's prompt renders it verbatim as
        # "Due: {due_date}". `assignments.due_date` is a DATETIME column, so
        # calling .isoformat() on it directly would put
        # "2026-09-01T00:00:00+00:00" into the prompt instead of "2026-09-01".
        due_date = row["due_date"]
        if due_date is not None and not isinstance(due_date, str):
            if hasattr(due_date, "date"):  # datetime -> date
                due_date = due_date.date()
            due_date = due_date.isoformat()

        # `assignments.maximum_score` is a FLOAT, but Dev C's AssignmentBrief
        # types it as int. Truncating with int() would silently turn a
        # maximum of 92.5 into 92 and show the learner the wrong total, so
        # narrow to int only when the value is exactly integral and keep the
        # float otherwise. Raised with Dev C to widen the annotation.
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
        detail: str | None = None,
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
            detail: free-form context for the reason (e.g. the top score).

        Raises:
            EscalationWriteError: if the row could not be written.
        """
        if not question or not question.strip():
            raise EscalationWriteError("Cannot escalate an empty question.")
        if reason is None:
            raise EscalationWriteError("An escalation requires a reason.")

        # Accept either the enum or its value, so a caller that has already
        # unwrapped it (or loaded one from JSON) still writes a valid row.
        reason_value = (
            reason.value if isinstance(reason, EscalationReason) else str(reason)
        )
        if not reason_value.strip():
            raise EscalationWriteError("An escalation requires a reason.")

        statement = text(
            f"""
            INSERT INTO {ESCALATIONS_TABLE}
                (learner_id, course_id, trainer_id, question,
                 reason, detail, status, created_at)
            VALUES
                (CAST(:learner_id AS INTEGER),
                 CAST(:course_id AS INTEGER),
                 CAST(:trainer_id AS INTEGER),
                 :question,
                 :reason,
                 :detail,
                 :status,
                 NOW())
            RETURNING id
            """
        )

        try:
            row = self.session.execute(
                statement,
                {
                    "learner_id": self.learner_id,
                    "course_id": int(course_id),
                    "trainer_id": (
                        int(trainer_id) if trainer_id is not None else None
                    ),
                    "question": question.strip(),
                    "reason": reason_value,
                    "detail": detail.strip() if detail else None,
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
            "Escalation %s created for learner=%s course=%s trainer=%s reason=%s",
            escalation_id,
            self.learner_id,
            course_id,
            trainer_id if trainer_id is not None else "unassigned",
            reason_value,
        )
        return escalation_id
