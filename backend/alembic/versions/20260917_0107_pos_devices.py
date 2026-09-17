"""POS device heartbeat table (last-seen monitoring).

Revision ID: 20260917_0107
Revises: 20260917_0106
Create Date: 2026-09-17
"""

from alembic import op
import sqlalchemy as sa

revision = "20260917_0107"
down_revision = "20260917_0106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_devices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("pending_queue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "device_id", name="uq_pos_devices_tenant_device"),
    )
    op.create_index("ix_pos_devices_tenant_id", "pos_devices", ["tenant_id"])
    op.create_index("ix_pos_devices_device_id", "pos_devices", ["device_id"])
    op.create_index("ix_pos_devices_store_id", "pos_devices", ["store_id"])
    op.create_index("ix_pos_devices_user_id", "pos_devices", ["user_id"])
    op.create_index("ix_pos_devices_last_seen_at", "pos_devices", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_pos_devices_last_seen_at", table_name="pos_devices")
    op.drop_index("ix_pos_devices_user_id", table_name="pos_devices")
    op.drop_index("ix_pos_devices_store_id", table_name="pos_devices")
    op.drop_index("ix_pos_devices_device_id", table_name="pos_devices")
    op.drop_index("ix_pos_devices_tenant_id", table_name="pos_devices")
    op.drop_table("pos_devices")
