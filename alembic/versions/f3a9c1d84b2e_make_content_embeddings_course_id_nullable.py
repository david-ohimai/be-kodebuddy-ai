"""make_content_embeddings_course_id_nullable

Revision ID: f3a9c1d84b2e
Revises: 95bb2c9b27c6
Create Date: 2026-08-25 10:00:00.000000

Decision: FAQs are global, not per-course (Option A from the Dev A/Dev B
schema review). course_id becomes nullable so a FAQ chunk can belong to
no single course; content_embeddings.search_content() already has the
SQL branch that treats a NULL course_id + content_type='faq' as globally
visible to every enrolled learner — this migration is what finally lets
that branch be reached instead of being dead code.

Curriculum and resource rows must still always carry a real course_id;
that's enforced in application code (ingest_curriculum.py), not the DB,
since Postgres has no clean way to make NULL conditional on another
column's value without a CHECK constraint we'd rather not maintain for
a one-week MVP.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a9c1d84b2e'
down_revision: Union[str, Sequence[str], None] = '95bb2c9b27c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'content_embeddings',
        'course_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    # NOTE: if any global (course_id IS NULL) FAQ rows exist when this runs,
    # the downgrade will fail on the NOT NULL constraint. Backfill or delete
    # those rows first — e.g.:
    #   DELETE FROM content_embeddings WHERE course_id IS NULL;
    op.alter_column(
        'content_embeddings',
        'course_id',
        existing_type=sa.Integer(),
        nullable=False,
    )