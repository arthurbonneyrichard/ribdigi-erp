"""Gym stage 1: trainers, training sessions, lockers, equipment, maintenance, guest visits.

Revision ID: 20261119_0190
Revises: 20261116_0189
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0190"
down_revision = "20261116_0189"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.String(36), primary_key=True)


def _tenant():
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def upgrade() -> None:
    op.create_table(
        "gym_trainers", _id(), _tenant(),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(40)), sa.Column("specialization", sa.String(150)),
        sa.Column("session_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "full_name", name="uq_gym_trainer_name"),
    )
    op.create_table(
        "gym_training_sessions", _id(), _tenant(),
        sa.Column("trainer_id", sa.String(36), sa.ForeignKey("gym_trainers.id"), nullable=False, index=True),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("gym_members.id"), nullable=False, index=True),
        sa.Column("starts_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("notes", sa.String(500)), sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "gym_lockers", _id(), _tenant(),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("member_id", sa.String(36), sa.ForeignKey("gym_members.id"), index=True),
        sa.Column("assigned_on", sa.Date()), sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "number", name="uq_gym_locker_number"),
    )
    op.create_table(
        "gym_equipment", _id(), _tenant(),
        sa.Column("name", sa.String(150), nullable=False), sa.Column("category", sa.String(80)),
        sa.Column("serial_number", sa.String(80)),
        sa.Column("status", sa.String(20), nullable=False, index=True), sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "gym_maintenance", _id(), _tenant(),
        sa.Column("equipment_id", sa.String(36), sa.ForeignKey("gym_equipment.id"), nullable=False, index=True),
        sa.Column("fault", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("resolution", sa.String(500)),
        sa.Column("opened_at", sa.DateTime()), sa.Column("closed_at", sa.DateTime()),
    )
    op.create_table(
        "gym_guest_visits", _id(), _tenant(),
        sa.Column("guest_name", sa.String(180), nullable=False), sa.Column("phone", sa.String(40)),
        sa.Column("host_member_id", sa.String(36), sa.ForeignKey("gym_members.id"), index=True),
        sa.Column("visited_at", sa.DateTime(), index=True), sa.Column("left_at", sa.DateTime()),
        sa.Column("created_by", sa.String(36)),
    )


def downgrade() -> None:
    for t in ("gym_guest_visits", "gym_maintenance", "gym_equipment", "gym_lockers", "gym_training_sessions", "gym_trainers"):
        op.drop_table(t)
