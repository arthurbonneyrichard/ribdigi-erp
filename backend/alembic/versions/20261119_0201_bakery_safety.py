"""Bakery food safety: temperature points, readings, signed checklists.

Revision ID: 20261119_0201
Revises: 20261119_0200
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0201"
down_revision = "20261119_0200"
branch_labels = None
depends_on = None


def _tenant():
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def upgrade() -> None:
    op.create_table(
        "bakery_safety_points", sa.Column("id", sa.String(36), primary_key=True), _tenant(),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("min_c", sa.Numeric(6, 1), nullable=False), sa.Column("max_c", sa.Numeric(6, 1), nullable=False),
        sa.Column("checks_per_day", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_bakery_safety_point_name"),
    )
    op.create_table(
        "bakery_safety_readings", sa.Column("id", sa.String(36), primary_key=True), _tenant(),
        sa.Column("point_id", sa.String(36), sa.ForeignKey("bakery_safety_points.id"), nullable=False, index=True),
        sa.Column("reading_c", sa.Numeric(6, 1), nullable=False),
        sa.Column("in_range", sa.Boolean(), nullable=False),
        sa.Column("action_taken", sa.String(500)), sa.Column("recorded_by", sa.String(36)),
        sa.Column("recorded_at", sa.DateTime(), index=True),
    )
    op.create_table(
        "bakery_safety_checks", sa.Column("id", sa.String(36), primary_key=True), _tenant(),
        sa.Column("kind", sa.String(20), nullable=False, index=True),
        sa.Column("check_date", sa.Date(), nullable=False, index=True),
        sa.Column("items", sa.JSON(), nullable=False), sa.Column("all_done", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(500)), sa.Column("signed_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime(), index=True),
    )


def downgrade() -> None:
    op.drop_table("bakery_safety_checks")
    op.drop_table("bakery_safety_readings")
    op.drop_table("bakery_safety_points")
