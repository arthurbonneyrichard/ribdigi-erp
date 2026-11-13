"""HRM headcount plans by department.

Revision ID: 20261113_0175
Revises: 20261113_0174
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0175"
down_revision = "20261113_0174"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hrm_headcount_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("department", sa.String(120), nullable=False),
        sa.Column("planned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "department", name="uq_hrm_headcount_department"),
    )


def downgrade() -> None:
    op.drop_table("hrm_headcount_plans")
