"""HRM: effective-dated PAYE / SSNIT / pension rates, Tier 2 and Tier 3 on payslips.

Revision ID: 20261112_0163
Revises: 20261112_0162
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261112_0163"
down_revision = "20261112_0162"
branch_labels = None
depends_on = None

ADD = {
    "hrm_employees": [
        ("ghana_card", sa.String(20), None),
        ("mobile_money", sa.String(20), None),
        ("tier3_percent", sa.Numeric(6, 3), "0"),
    ],
    "hrm_payroll_runs": [
        ("tier2", sa.Numeric(14, 2), "0"),
        ("tier3", sa.Numeric(14, 2), "0"),
        ("statutory_rate_id", sa.String(36), None),
        ("tier2_paid_at", sa.DateTime(), None),
        ("tier3_paid_at", sa.DateTime(), None),
    ],
    "hrm_payslips": [
        ("tier3_percent", sa.Numeric(6, 3), "0"),
        ("tier1", sa.Numeric(14, 2), "0"),
        ("tier2", sa.Numeric(14, 2), "0"),
        ("tier3", sa.Numeric(14, 2), "0"),
        ("tier3_relief", sa.Numeric(14, 2), "0"),
        ("rates_used", sa.JSON(), None),
    ],
}


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    if "hrm_statutory_rates" not in tables:
        op.create_table(
            "hrm_statutory_rates",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("effective_from", sa.Date(), nullable=False, index=True),
            sa.Column("employee_percent", sa.Numeric(6, 3), nullable=False),
            sa.Column("employer_percent", sa.Numeric(6, 3), nullable=False),
            sa.Column("tier2_percent", sa.Numeric(6, 3), nullable=False, server_default="0"),
            sa.Column("insurable_cap", sa.Numeric(14, 2), nullable=True),
            sa.Column("tier3_relief_percent", sa.Numeric(6, 3), nullable=False, server_default="16.5"),
            sa.Column("paye_bands", sa.JSON(), nullable=False),
            sa.Column("rounding", sa.String(16), nullable=False, server_default="half_up"),
            sa.Column("source_note", sa.String(255), nullable=True),
            sa.Column("created_by", sa.String(36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "effective_from", name="uq_hrm_statutory_from"),
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
    if "hrm_statutory_rates" in tables:
        op.drop_table("hrm_statutory_rates")
