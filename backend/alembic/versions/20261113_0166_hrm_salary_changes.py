"""HRM: salary history from a date, corrections to approved pay carried into the next payroll.

Revision ID: 20261113_0166
Revises: 20261113_0165
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0166"
down_revision = "20261113_0165"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "hrm_salary_changes" not in tables:
        op.create_table(
            "hrm_salary_changes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
            sa.Column("effective_from", sa.Date(), nullable=False, index=True),
            sa.Column("basic_salary", sa.Numeric(14, 2), nullable=False),
            sa.Column("allowances", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("reason", sa.String(255), nullable=False),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("employee_id", "effective_from", name="uq_hrm_salary_change_from"),
        )
    if "hrm_payroll_adjustments" not in tables:
        op.create_table(
            "hrm_payroll_adjustments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("for_period", sa.String(7), nullable=True),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("reason", sa.String(255), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending", index=True),
            sa.Column("run_id", sa.String(36), nullable=True, index=True),
            sa.Column("salary_change_id", sa.String(36), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )
    if "hrm_payslips" in tables:
        have = {c["name"] for c in insp.get_columns("hrm_payslips")}
        for name in ("arrears_basic", "adjustment"):
            if name not in have:
                op.add_column("hrm_payslips", sa.Column(name, sa.Numeric(14, 2), nullable=True, server_default="0"))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "hrm_payslips" in tables:
        have = {c["name"] for c in insp.get_columns("hrm_payslips")}
        for name in ("adjustment", "arrears_basic"):
            if name in have:
                op.drop_column("hrm_payslips", name)
    for table in ("hrm_payroll_adjustments", "hrm_salary_changes"):
        if table in tables:
            op.drop_table(table)
