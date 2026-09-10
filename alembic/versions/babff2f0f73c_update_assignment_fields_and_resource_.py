"""update assignment fields and resource type

Revision ID: babff2f0f73c
Revises: 755b676f1992
Create Date: 2026-08-27 14:26:22.030099
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "babff2f0f73c"
down_revision: Union[str, Sequence[str], None] = "755b676f1992"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add assignment instructions and requirements.
    op.add_column(
        "assignments",
        sa.Column(
            "instructions",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "assignments",
        sa.Column(
            "requirements",
            sa.JSON(),
            nullable=True,
        ),
    )

    # Change resource type from PostgreSQL ENUM to VARCHAR.
    op.alter_column(
        "resources",
        "type",
        existing_type=postgresql.ENUM(
            "LINK",
            "PDF",
            "GITHUB_REPO",
            "VIDEO",
            name="resourcetype",
        ),
        type_=sa.String(length=100),
        existing_nullable=False,
        postgresql_using="type::text",
    )

    # Remove the old PostgreSQL enum type.
    op.execute("DROP TYPE IF EXISTS resourcetype")

    # Resource URL is intentionally nullable.
    op.alter_column(
        "resources",
        "url",
        existing_type=sa.VARCHAR(),
        nullable=True,
    )


def downgrade() -> None:
    # Restore resource URL to NOT NULL.
    op.alter_column(
        "resources",
        "url",
        existing_type=sa.VARCHAR(),
        nullable=False,
    )

    # Re-create the PostgreSQL enum.
    resource_type_enum = postgresql.ENUM(
        "LINK",
        "PDF",
        "GITHUB_REPO",
        "VIDEO",
        name="resourcetype",
    )

    resource_type_enum.create(op.get_bind(), checkfirst=True)

    # Convert VARCHAR back to the enum.
    op.alter_column(
        "resources",
        "type",
        existing_type=sa.String(length=100),
        type_=resource_type_enum,
        existing_nullable=False,
        postgresql_using="type::resourcetype",
    )

    # Remove assignment JSON columns.
    op.drop_column("assignments", "requirements")
    op.drop_column("assignments", "instructions")