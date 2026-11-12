"""HRM: public holidays, staff loans and salary advances, two-person payroll rule.

Revision ID: 20261113_0164
Revises: 20261112_0163
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0164"
down_revision = "20261112_0163"
branch_labels = None
depends_on = None

ADD = {
    "hrm_settings": [("two_person_payroll", sa.Boolean(), sa.false())],
    "hrm_payroll_runs": [("loan_deductions", sa.Numeric(14, 2), "0")],
    "hrm_payslips": [("loan_deduction", sa.Numeric(14, 2), "0")],
}


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "hrm_holidays" not in tables:
        op.create_table(
            "hrm_holidays",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("day", sa.Date(), nullable=False, index=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "day", name="uq_hrm_holiday_day"),
        )
    if "hrm_loans" not in tables:
        op.create_table(
            "hrm_loans",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
            sa.Column("loan_number", sa.String(40), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("principal", sa.Numeric(14, 2), nullable=False),
            sa.Column("monthly_deduction", sa.Numeric(14, 2), nullable=False),
            sa.Column("balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("first_period", sa.String(7), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending", index=True),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("decision_note", sa.String(255), nullable=True),
            sa.Column("requested_by", sa.String(36), nullable=True),
            sa.Column("decided_by", sa.String(36), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.Column("paid_out_at", sa.DateTime(), nullable=True),
            sa.Column("paid_out_method", sa.String(20), nullable=True),
            sa.Column("journal_entry_id", sa.String(36), nullable=True),
            sa.Column("settled_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "loan_number", name="uq_hrm_loan_number"),
        )
    if "hrm_loan_repayments" not in tables:
        op.create_table(
            "hrm_loan_repayments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("loan_id", sa.String(36), sa.ForeignKey("hrm_loans.id"), nullable=False, index=True),
            sa.Column("payslip_id", sa.String(36), nullable=True),
            sa.Column("run_id", sa.String(36), nullable=True),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("source", sa.String(16), nullable=False),
            sa.Column("method", sa.String(20), nullable=True),
            sa.Column("journal_entry_id", sa.String(36), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("loan_id", "payslip_id", name="uq_hrm_loan_repayment_slip"),
        )
    for table, cols in ADD.items():
        if table not in tables:
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        for name, kind, default in cols:
            if name not in have:
                op.add_column(table, sa.Column(name, kind, nullable=True, server_default=default))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    for table, cols in ADD.items():
        if table not in tables:
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        for name, _kind, _default in cols:
            if name in have:
                op.drop_column(table, name)
    for table in ("hrm_loan_repayments", "hrm_loans", "hrm_holidays"):
        if table in tables:
            op.drop_table(table)
