"""Journal entry supporting document attachment (BR-10.2).

Revision ID: 20260812_0076
Revises: 20260812_0075
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0076"
down_revision = "20260812_0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "journal_entries",
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("journal_entries", "attachment_url")
