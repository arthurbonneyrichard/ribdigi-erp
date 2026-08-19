"""Journal entry supporting documents (Stage 9 J1)

Revision ID: 20260809_0083
Revises: 20260809_0082
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0083"
down_revision = "20260809_0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("journal_entries") as batch:
        batch.add_column(sa.Column("attachment_url", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("journal_entries") as batch:
        batch.drop_column("attachment_url")
