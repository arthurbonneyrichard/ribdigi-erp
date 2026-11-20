"""Gym door: credentials, devices, offline door events.

Revision ID: 20261119_0197
Revises: 20261119_0196g
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0197"
down_revision = "20261119_0196g"
branch_labels = None
depends_on = None


def _fk(name, table, nullable=False):
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=nullable, index=True)


def upgrade() -> None:
    op.create_table(
        "gym_credentials", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"), _fk("member_id", "gym_members"),
        sa.Column("kind", sa.String(20), nullable=False, server_default="qr"), sa.Column("label", sa.String(80)),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()), sa.Column("revoked_at", sa.DateTime()),
    )
    op.create_table(
        "gym_devices", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"), _fk("branch_id", "gym_branches", True),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("kind", sa.String(20), nullable=False, server_default="qr_scanner"),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime()), sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "gym_door_events", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"),
        sa.Column("event_id", sa.String(64), nullable=False), _fk("device_id", "gym_devices", True), _fk("member_id", "gym_members", True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False), sa.Column("outcome", sa.String(20), nullable=False, index=True),
        sa.Column("message", sa.String(200)),
        sa.Column("needs_attention", sa.Boolean(), nullable=False, server_default=sa.false(), index=True),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "event_id", name="uq_gym_door_event"),
    )


def downgrade() -> None:
    for t in ("gym_door_events", "gym_devices", "gym_credentials"):
        op.drop_table(t)
