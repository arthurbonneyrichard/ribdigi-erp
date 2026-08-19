"""Journal entry store dimension (Stage 14 A1)

Revision ID: 20260810_0087
Revises: 20260810_0086
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa

revision = "20260810_0087"
down_revision = "20260810_0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("journal_entries") as batch:
        batch.add_column(
            sa.Column(
                "store_id",
                sa.String(length=36),
                sa.ForeignKey("stores.id"),
                nullable=True,
            )
        )
        batch.create_index("ix_journal_entries_store_id", ["store_id"])


def downgrade() -> None:
    with op.batch_alter_table("journal_entries") as batch:
        batch.drop_index("ix_journal_entries_store_id")
        batch.drop_column("store_id")
