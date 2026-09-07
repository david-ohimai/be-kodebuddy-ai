"""create cohort mentors table

Revision ID: ec7e156c6c6d
Revises: 88fb431c899e
Create Date: 2026-09-06 21:39:48.439583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec7e156c6c6d'
down_revision: Union[str, Sequence[str], None] = '88fb431c899e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cohort_mentors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cohort_id", sa.Integer(), nullable=False),
        sa.Column("mentor_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False,),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True,),
        sa.ForeignKeyConstraint(["cohort_id"], ["cohorts.id"],),
        sa.ForeignKeyConstraint(["mentor_id"], ["users.id"],),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cohort_id", "mentor_id", name="uq_cohort_mentor",),)

    op.create_index("ix_cohort_mentors_cohort_id", "cohort_mentors", ["cohort_id"], unique=False,)
    op.create_index("ix_cohort_mentors_mentor_id", "cohort_mentors", ["mentor_id"], unique=False,)


def downgrade() -> None:
    op.drop_index("ix_cohort_mentors_mentor_id", table_name="cohort_mentors",)
    op.drop_index("ix_cohort_mentors_cohort_id",table_name="cohort_mentors",)
    op.drop_table("cohort_mentors")