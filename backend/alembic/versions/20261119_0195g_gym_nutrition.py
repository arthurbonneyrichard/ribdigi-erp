"""Gym nutrition: member plans and daily intake logs.

Revision ID: 20261119_0195g
Revises: 20261119_0196
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0195g"
down_revision = "20261119_0196"
branch_labels = None
depends_on = None


def _fk(name, table):
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=False, index=True)


def upgrade() -> None:
    op.create_table(
        "gym_nutrition_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        _fk("tenant_id", "tenants"), _fk("member_id", "gym_members"),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("calories", sa.Integer()), sa.Column("protein_g", sa.Integer()), sa.Column("carbs_g", sa.Integer()),
        sa.Column("fat_g", sa.Integer()), sa.Column("water_ml", sa.Integer()),
        sa.Column("allergies", sa.String(300)), sa.Column("preferences", sa.String(300)), sa.Column("meals", sa.Text()),
        sa.Column("starts_on", sa.Date(), nullable=False), sa.Column("ends_on", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )
    op.create_table(
        "gym_nutrition_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        _fk("tenant_id", "tenants"), _fk("plan_id", "gym_nutrition_plans"), _fk("member_id", "gym_members"),
        sa.Column("logged_on", sa.Date(), nullable=False, index=True),
        sa.Column("calories", sa.Integer()), sa.Column("protein_g", sa.Integer()), sa.Column("carbs_g", sa.Integer()),
        sa.Column("fat_g", sa.Integer()), sa.Column("water_ml", sa.Integer()),
        sa.Column("recorded_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("plan_id", "logged_on", name="uq_gym_nutrition_log_day"),
    )


def downgrade() -> None:
    op.drop_table("gym_nutrition_logs")
    op.drop_table("gym_nutrition_plans")
