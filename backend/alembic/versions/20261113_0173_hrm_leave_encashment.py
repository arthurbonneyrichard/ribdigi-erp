"""HRM leave encashment: unused annual leave paid on payroll.

Revision ID: 20261113_0173
Revises: 20261113_0172
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0173"
down_revision = "20261113_0172"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hrm_leave_encashments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("day_rate", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("period", sa.String(7), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="approved", index=True),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("run_id", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table("hrm_payslips") as batch:
        batch.add_column(sa.Column("leave_pay", sa.Numeric(14, 2), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("hrm_payslips") as batch:
        batch.drop_column("leave_pay")
    op.drop_table("hrm_leave_encashments")
