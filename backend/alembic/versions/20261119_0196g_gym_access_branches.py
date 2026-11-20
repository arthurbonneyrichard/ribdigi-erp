"""Gym: branches, per-plan access rules, recurring class series.

Revision ID: 20261119_0196g
Revises: 20261119_0195g
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0196g"
down_revision = "20261119_0195g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gym_branches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("code", sa.String(20), nullable=False), sa.Column("name", sa.String(150), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "code", name="uq_gym_branch_code"),
    )
    op.add_column("gym_plans", sa.Column("access_start", sa.String(5)))
    op.add_column("gym_plans", sa.Column("access_end", sa.String(5)))
    op.add_column("gym_plans", sa.Column("access_days", sa.String(20)))
    op.add_column("gym_plans", sa.Column("branch_scope", sa.String(10), nullable=False, server_default="all"))
    op.add_column("gym_members", sa.Column("home_branch_id", sa.String(36), sa.ForeignKey("gym_branches.id")))
    op.create_index("ix_gym_members_home_branch_id", "gym_members", ["home_branch_id"])
    op.add_column("gym_check_ins", sa.Column("branch_id", sa.String(36), sa.ForeignKey("gym_branches.id")))
    op.create_index("ix_gym_check_ins_branch_id", "gym_check_ins", ["branch_id"])
    op.add_column("gym_classes", sa.Column("series_id", sa.String(36)))
    op.create_index("ix_gym_classes_series_id", "gym_classes", ["series_id"])


def downgrade() -> None:
    op.drop_index("ix_gym_classes_series_id", "gym_classes")
    op.drop_column("gym_classes", "series_id")
    op.drop_index("ix_gym_check_ins_branch_id", "gym_check_ins")
    op.drop_column("gym_check_ins", "branch_id")
    op.drop_index("ix_gym_members_home_branch_id", "gym_members")
    op.drop_column("gym_members", "home_branch_id")
    for c in ("branch_scope", "access_days", "access_end", "access_start"):
        op.drop_column("gym_plans", c)
    op.drop_table("gym_branches")
