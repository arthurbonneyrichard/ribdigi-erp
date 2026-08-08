"""sales invoices and customer payments

Revision ID: 20260808_0003
Revises: 20260808_0002
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0003"
down_revision = "20260808_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_invoices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("invoice_number", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "invoice_number"),
    )
    op.create_index("ix_sales_invoices_tenant_id", "sales_invoices", ["tenant_id"])
    op.create_index("ix_sales_invoices_customer_id", "sales_invoices", ["customer_id"])

    op.create_table(
        "sales_invoice_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("sales_invoice_id", sa.String(length=36), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
    )
    op.create_index("ix_sales_invoice_items_invoice", "sales_invoice_items", ["sales_invoice_id"])

    op.create_table(
        "customer_payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("payment_number", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("sales_invoice_id", sa.String(length=36), sa.ForeignKey("sales_invoices.id"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=40), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "payment_number"),
    )
    op.create_index("ix_customer_payments_customer", "customer_payments", ["customer_id"])


def downgrade() -> None:
    op.drop_table("customer_payments")
    op.drop_table("sales_invoice_items")
    op.drop_table("sales_invoices")
