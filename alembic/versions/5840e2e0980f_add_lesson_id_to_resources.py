"""add lesson id to resources

Revision ID: 5840e2e0980f
Revises: bbd9a4af881b
Create Date: 2026-09-08 04:01:52.399169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5840e2e0980f'
down_revision: Union[str, Sequence[str], None] = 'bbd9a4af881b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("resources", sa.Column("lesson_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_resources_lesson_id"), "resources", ["lesson_id"], unique=False)
    op.create_foreign_key("fk_resources_lesson_id_lessons", "resources", "lessons", ["lesson_id"], ["id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_resources_lesson_id_lessons", "resources", type_="foreignkey")
    op.drop_index(op.f("ix_resources_lesson_id"), table_name="resources")
    op.drop_column("resources", "lesson_id")
