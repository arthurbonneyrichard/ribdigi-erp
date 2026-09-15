"""Offline device remote wipe columns (scaffold — Offline Complete still MISSING).

Revision ID: 20260914_0111
Revises: 20260828_0110
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0111"
down_revision = "20260828_0110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("offline_devices", sa.Column("wipe_requested_at", sa.DateTime(), nullable=True))
    op.add_column(
        "offline_devices",
        sa.Column("wipe_requested_by", sa.String(length=36), nullable=True),
    )
    op.add_column("offline_devices", sa.Column("wipe_acked_at", sa.DateTime(), nullable=True))
    op.add_column(
        "offline_devices",
        sa.Column("wipe_status", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("offline_devices", "wipe_status")
    op.drop_column("offline_devices", "wipe_acked_at")
    op.drop_column("offline_devices", "wipe_requested_by")
    op.drop_column("offline_devices", "wipe_requested_at")
