"""HRM: sales commission percent per person, approved monthly commission paid on payroll.

Revision ID: 20261113_0169
Revises: 20261113_0168
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0169"
down_revision = "20261113_0168"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "hrm_commissions" not in tables:
        op.create_table(
            "hrm_commissions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
            sa.Column("period", sa.String(7), nullable=False, index=True),
            sa.Column("net_sales", sa.Numeric(14, 2), nullable=False),
            sa.Column("percent", sa.Numeric(6, 3), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="approved", index=True),
            sa.Column("run_id", sa.String(36), nullable=True),
            sa.Column("approved_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("employee_id", "period", name="uq_hrm_commission_month"),
        )
    for table, name in (("hrm_employees", "commission_percent"), ("hrm_payslips", "commission")):
        if table in tables and name not in {c["name"] for c in insp.get_columns(table)}:
            kind = sa.Numeric(6, 3) if name == "commission_percent" else sa.Numeric(14, 2)
            op.add_column(table, sa.Column(name, kind, nullable=True, server_default="0"))


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    for table, name in (("hrm_payslips", "commission"), ("hrm_employees", "commission_percent")):
        if table in tables and name in {c["name"] for c in insp.get_columns(table)}:
            op.drop_column(table, name)
    if "hrm_commissions" in tables:
        op.drop_table("hrm_commissions")
