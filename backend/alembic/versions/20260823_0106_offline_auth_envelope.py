"""Offline device 7-day authorization envelope columns (§13–14).

Revision ID: 20260823_0106
Revises: 20260816_0105
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260823_0106"
down_revision = "20260816_0105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "offline_devices",
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=True),
    )
    op.add_column("offline_devices", sa.Column("bound_user_id", sa.String(length=36), nullable=True))
    op.add_column("offline_devices", sa.Column("bound_store_id", sa.String(length=36), nullable=True))
    op.add_column(
        "offline_devices",
        sa.Column("permissions_snapshot", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column("offline_devices", sa.Column("envelope_issued_at", sa.DateTime(), nullable=True))
    op.add_column("offline_devices", sa.Column("last_online_at", sa.DateTime(), nullable=True))
    op.add_column("offline_devices", sa.Column("offline_authorized_until", sa.DateTime(), nullable=True))
    op.add_column("offline_devices", sa.Column("catalog_version", sa.String(length=64), nullable=True))
    op.add_column("offline_devices", sa.Column("app_version", sa.String(length=40), nullable=True))
    op.create_index("ix_offline_devices_company_id", "offline_devices", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_offline_devices_company_id", table_name="offline_devices")
    op.drop_column("offline_devices", "app_version")
    op.drop_column("offline_devices", "catalog_version")
    op.drop_column("offline_devices", "offline_authorized_until")
    op.drop_column("offline_devices", "last_online_at")
    op.drop_column("offline_devices", "envelope_issued_at")
    op.drop_column("offline_devices", "permissions_snapshot")
    op.drop_column("offline_devices", "bound_store_id")
    op.drop_column("offline_devices", "bound_user_id")
    op.drop_column("offline_devices", "company_id")
