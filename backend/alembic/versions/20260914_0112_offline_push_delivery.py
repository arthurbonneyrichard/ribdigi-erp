"""Offline Web Push subscriptions + delivery log (wipe push PARTIAL — not Offline Complete).

Revision ID: 20260914_0112
Revises: 20260914_0111
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0112"
down_revision = "20260914_0111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offline_push_subscriptions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "device_id",
            sa.String(length=36),
            sa.ForeignKey("offline_devices.id"),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(length=2000), nullable=False),
        sa.Column("p256dh", sa.String(length=255), nullable=False),
        sa.Column("auth", sa.String(length=255), nullable=False),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "device_id", name="uq_offline_push_sub_tenant_device"),
    )
    op.create_index(
        "ix_offline_push_subscriptions_tenant_id",
        "offline_push_subscriptions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_offline_push_subscriptions_device_id",
        "offline_push_subscriptions",
        ["device_id"],
    )

    op.create_table(
        "offline_push_deliveries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "device_id",
            sa.String(length=36),
            sa.ForeignKey("offline_devices.id"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            sa.String(length=36),
            sa.ForeignKey("offline_push_subscriptions.id"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_offline_push_deliveries_tenant_id",
        "offline_push_deliveries",
        ["tenant_id"],
    )
    op.create_index(
        "ix_offline_push_deliveries_device_id",
        "offline_push_deliveries",
        ["device_id"],
    )
    op.create_index(
        "ix_offline_push_deliveries_event_type",
        "offline_push_deliveries",
        ["event_type"],
    )
    op.create_index(
        "ix_offline_push_deliveries_status",
        "offline_push_deliveries",
        ["status"],
    )


def downgrade() -> None:
    op.drop_table("offline_push_deliveries")
    op.drop_table("offline_push_subscriptions")
