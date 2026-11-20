"""FMCG offline sync: one row per action sent from a device.

Revision ID: 20261120_0225f
Revises: 20261120_0224f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0225f"
down_revision = "20261120_0224f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fmcg_offline_refs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("ref", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True, index=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("result_id", sa.String(36), nullable=True),
        sa.Column("message", sa.String(300), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "ref", name="uq_fmcg_offline_ref"),
    )


def downgrade() -> None:
    op.drop_table("fmcg_offline_refs")
