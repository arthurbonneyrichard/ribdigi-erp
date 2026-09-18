"""POS device heartbeat table (last-seen monitoring).

Revision ID: 20260917_0107
Revises: 20260917_0106
Create Date: 2026-09-17

Idempotent: skip create when table/indexes already exist.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260917_0107"
down_revision = "20260917_0106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "pos_devices" not in tables:
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
        insp = sa.inspect(bind)

    existing_ix = {ix["name"] for ix in (insp.get_indexes("pos_devices") or []) if ix.get("name")}
    for name, cols in (
        ("ix_pos_devices_tenant_id", ["tenant_id"]),
        ("ix_pos_devices_device_id", ["device_id"]),
        ("ix_pos_devices_store_id", ["store_id"]),
        ("ix_pos_devices_user_id", ["user_id"]),
        ("ix_pos_devices_last_seen_at", ["last_seen_at"]),
    ):
        if name not in existing_ix:
            op.create_index(name, "pos_devices", cols)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "pos_devices" not in set(insp.get_table_names()):
        return
    existing_ix = {ix["name"] for ix in (insp.get_indexes("pos_devices") or []) if ix.get("name")}
    for name in (
        "ix_pos_devices_last_seen_at",
        "ix_pos_devices_user_id",
        "ix_pos_devices_store_id",
        "ix_pos_devices_device_id",
        "ix_pos_devices_tenant_id",
    ):
        if name in existing_ix:
            op.drop_index(name, table_name="pos_devices")
    op.drop_table("pos_devices")
