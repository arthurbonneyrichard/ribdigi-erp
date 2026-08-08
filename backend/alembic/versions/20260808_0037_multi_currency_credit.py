"""multi-currency credit: exchange rates + document currency

Revision ID: 20260808_0037
Revises: 20260808_0036
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0037"
down_revision = "20260808_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("currency_code", sa.String(length=10), nullable=False),
        sa.Column("rate_to_base", sa.Numeric(18, 8), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "currency_code"),
    )
    for table in ("sales_invoices", "purchase_invoices", "customer_payments", "supplier_payments"):
        op.add_column(table, sa.Column("currency", sa.String(length=10), nullable=False, server_default=""))
        op.add_column(
            table,
            sa.Column("exchange_rate", sa.Numeric(18, 8), nullable=False, server_default="1"),
        )
    for table in ("customer_payments", "supplier_payments"):
        op.add_column(
            table,
            sa.Column("fx_gain_loss", sa.Numeric(14, 2), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for table in ("customer_payments", "supplier_payments"):
        op.drop_column(table, "fx_gain_loss")
    for table in ("sales_invoices", "purchase_invoices", "customer_payments", "supplier_payments"):
        op.drop_column(table, "exchange_rate")
        op.drop_column(table, "currency")
    op.drop_table("exchange_rates")
