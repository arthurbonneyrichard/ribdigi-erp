"""Restaurant tips: a tip on each bill, tip share-outs and their shares, tips on payslips.

Revision ID: 20261113_0171
Revises: 20261113_0170
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0171"
down_revision = "20261113_0170"
branch_labels = None
depends_on = None

MONEY = sa.Numeric(14, 2)


def upgrade() -> None:
    with op.batch_alter_table("restaurant_orders") as batch:
        batch.add_column(sa.Column("tip_amount", MONEY, nullable=False, server_default="0"))
        batch.add_column(sa.Column("tip_run_id", sa.String(36), nullable=True))
    op.create_index("ix_restaurant_orders_tip_run_id", "restaurant_orders", ["tip_run_id"])
    for table in ("hrm_payslips", "hrm_payroll_runs"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("tips", MONEY, nullable=False, server_default="0"))
    op.create_table(
        "restaurant_tip_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("run_number", sa.String(40), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("pay_by", sa.String(20), nullable=False, server_default="cash"),
        sa.Column("period", sa.String(7), nullable=True),
        sa.Column("total", MONEY, nullable=False, server_default="0"),
        sa.Column("tip_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft", index=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("paid_method", sa.String(32), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "run_number", name="uq_restaurant_tip_run_number"),
    )
    op.create_table(
        "restaurant_tip_shares",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("restaurant_tip_runs.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.String(36), nullable=True, index=True),
        sa.Column("basis", MONEY, nullable=False, server_default="0"),
        sa.Column("amount", MONEY, nullable=False, server_default="0"),
        sa.Column("payroll_run_id", sa.String(36), nullable=True, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.UniqueConstraint("run_id", "user_id", name="uq_restaurant_tip_share_person"),
    )


def downgrade() -> None:
    op.drop_table("restaurant_tip_shares")
    op.drop_table("restaurant_tip_runs")
    for table in ("hrm_payroll_runs", "hrm_payslips"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("tips")
    op.drop_index("ix_restaurant_orders_tip_run_id", table_name="restaurant_orders")
    with op.batch_alter_table("restaurant_orders") as batch:
        batch.drop_column("tip_run_id")
        batch.drop_column("tip_amount")
