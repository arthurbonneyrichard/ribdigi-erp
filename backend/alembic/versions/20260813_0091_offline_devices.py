"""Add offline_devices for Stage 163 V1 device registration.

Revision ID: 20260813_0091
Revises: 20260812_0090
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_0091"
down_revision = "20260812_0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "offline_devices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("device_code", sa.String(length=64), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("registered_by", sa.String(length=36), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "device_code"),
    )
    op.create_index("ix_offline_devices_tenant_id", "offline_devices", ["tenant_id"])
    op.create_index("ix_offline_devices_device_code", "offline_devices", ["device_code"])


def downgrade() -> None:
    op.drop_index("ix_offline_devices_device_code", table_name="offline_devices")
    op.drop_index("ix_offline_devices_tenant_id", table_name="offline_devices")
    op.drop_table("offline_devices")
