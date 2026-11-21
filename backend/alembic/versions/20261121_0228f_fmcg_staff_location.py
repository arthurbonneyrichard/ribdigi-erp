"""FMCG staff location: per-person sharing switch and the last position, plus 30 days of pings.

Revision ID: 20261121_0228f
Revises: 20261121_0227r
Create Date: 2026-11-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261121_0228f"
down_revision = "20261121_0227r"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fmcg_track_state",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled_by", sa.String(36), nullable=True),
        sa.Column("enabled_at", sa.DateTime(), nullable=True),
        sa.Column("notice_ack_at", sa.DateTime(), nullable=True),
        sa.Column("last_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("last_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("last_accuracy_m", sa.Numeric(8, 1), nullable=True),
        sa.Column("last_speed_kmh", sa.Numeric(6, 1), nullable=True),
        sa.Column("last_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_fmcg_track_state_user"),
    )
    op.create_table(
        "fmcg_track_pings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("accuracy_m", sa.Numeric(8, 1), nullable=True),
        sa.Column("speed_kmh", sa.Numeric(6, 1), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", "captured_at", name="uq_fmcg_track_ping"),
    )
    op.create_index("ix_fmcg_track_pings_user_time", "fmcg_track_pings", ["tenant_id", "user_id", "captured_at"])


def downgrade() -> None:
    op.drop_index("ix_fmcg_track_pings_user_time", table_name="fmcg_track_pings")
    op.drop_table("fmcg_track_pings")
    op.drop_table("fmcg_track_state")
