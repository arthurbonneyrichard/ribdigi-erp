"""HRM field staff profile (FMCG).

Revision ID: 20261119_0195
Revises: 20261119_0194
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0195"
down_revision = "20261119_0194"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hrm_field_staff",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("field_role", sa.String(16), nullable=False),
        sa.Column("monthly_sales_target", sa.Numeric(16, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("employee_id", name="uq_hrm_field_staff_person"),
    )


def downgrade() -> None:
    op.drop_table("hrm_field_staff")
