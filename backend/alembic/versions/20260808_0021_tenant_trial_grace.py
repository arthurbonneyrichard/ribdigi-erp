"""tenant trial grace lifecycle

Revision ID: 20260808_0021
Revises: 20260808_0020
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0021"
down_revision = "20260808_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("trial_ends_at", sa.DateTime(), nullable=True))
    op.add_column("tenants", sa.Column("grace_ends_at", sa.DateTime(), nullable=True))
    op.add_column("tenants", sa.Column("trial_notices", sa.JSON(), nullable=True))
    # Backfill: active trials get 14 days from created_at
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "postgresql":
        op.execute(
            sa.text(
                "UPDATE tenants SET trial_ends_at = created_at + INTERVAL '14 days' "
                "WHERE status = 'trial' AND trial_ends_at IS NULL"
            )
        )
    else:
        # SQLite / others: approximate with datetime('now') fallback via Python not available;
        # leave null; ensure_trial_state / register set dates for new tenants.
        op.execute(
            sa.text(
                "UPDATE tenants SET trial_ends_at = datetime(created_at, '+14 days') "
                "WHERE status = 'trial' AND trial_ends_at IS NULL"
            )
        )


def downgrade() -> None:
    op.drop_column("tenants", "trial_notices")
    op.drop_column("tenants", "grace_ends_at")
    op.drop_column("tenants", "trial_ends_at")
