"""FMCG alert log: one row per alert band sent.

Revision ID: 20261120_0224f
Revises: 20261120_0223f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0224f"
down_revision = "20261120_0223f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fmcg_alert_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("ref_id", sa.String(80), nullable=False),
        sa.Column("band", sa.Integer(), nullable=False),
        sa.Column("summary", sa.String(200), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "kind", "ref_id", "band", name="uq_fmcg_alert_band"),
    )


def downgrade() -> None:
    op.drop_table("fmcg_alert_log")
