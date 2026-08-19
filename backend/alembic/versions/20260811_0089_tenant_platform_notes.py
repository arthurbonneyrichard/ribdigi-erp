"""Add platform_notes for House operator notes (Stage 87 Y1)

Revision ID: 20260811_0089
Revises: 20260811_0088
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa

revision = "20260811_0089"
down_revision = "20260811_0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("platform_notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "platform_notes")
