"""Gym facilities and facility bookings.

Revision ID: 20261119_0207g
Revises: 20261119_0206g
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0207g"
down_revision = "20261119_0206g"
branch_labels = None
depends_on = None


def _fk(name, table, nullable=False):
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=nullable, index=True)


def upgrade() -> None:
    op.create_table(
        "gym_facilities", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"), _fk("branch_id", "gym_branches", True),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("kind", sa.String(20), nullable=False, server_default="other"),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("open_time", sa.String(5), nullable=False, server_default="06:00"),
        sa.Column("close_time", sa.String(5), nullable=False, server_default="22:00"),
        sa.Column("max_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_gym_facility_name"),
    )
    op.create_table(
        "gym_facility_bookings", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"),
        _fk("facility_id", "gym_facilities"), _fk("member_id", "gym_members"),
        sa.Column("starts_at", sa.DateTime(), nullable=False, index=True), sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="booked", index=True),
        sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("gym_facility_bookings")
    op.drop_table("gym_facilities")
