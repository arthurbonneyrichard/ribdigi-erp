"""early payment discount terms

Revision ID: 20260808_0032
Revises: 20260808_0031
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0032"
down_revision = "20260808_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("early_pay_discount_pct", sa.Numeric(7, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenants",
        sa.Column("early_pay_discount_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "customer_payments",
        sa.Column("early_payment_discount", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("customer_payments", "early_payment_discount")
    op.drop_column("tenants", "early_pay_discount_days")
    op.drop_column("tenants", "early_pay_discount_pct")
