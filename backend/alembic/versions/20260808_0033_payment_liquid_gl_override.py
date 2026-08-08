"""per-payment liquid GL account override

Revision ID: 20260808_0033
Revises: 20260808_0032
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0033"
down_revision = "20260808_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_payments",
        sa.Column("liquid_account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
    )
    op.create_index("ix_customer_payments_liquid_account_id", "customer_payments", ["liquid_account_id"])
    op.add_column(
        "supplier_payments",
        sa.Column("liquid_account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
    )
    op.create_index("ix_supplier_payments_liquid_account_id", "supplier_payments", ["liquid_account_id"])
    op.add_column(
        "expenses",
        sa.Column("liquid_account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
    )
    op.create_index("ix_expenses_liquid_account_id", "expenses", ["liquid_account_id"])


def downgrade() -> None:
    op.drop_index("ix_expenses_liquid_account_id", table_name="expenses")
    op.drop_column("expenses", "liquid_account_id")
    op.drop_index("ix_supplier_payments_liquid_account_id", table_name="supplier_payments")
    op.drop_column("supplier_payments", "liquid_account_id")
    op.drop_index("ix_customer_payments_liquid_account_id", table_name="customer_payments")
    op.drop_column("customer_payments", "liquid_account_id")
