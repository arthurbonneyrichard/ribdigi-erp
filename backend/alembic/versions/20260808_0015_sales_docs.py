"""sales quotations, orders, returns

Revision ID: 20260808_0015
Revises: 20260808_0014
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0015"
down_revision = "20260808_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_invoices", sa.Column("quotation_id", sa.String(length=36), nullable=True))
    op.add_column("sales_invoices", sa.Column("sales_order_id", sa.String(length=36), nullable=True))
    op.create_index("ix_sales_invoices_quotation_id", "sales_invoices", ["quotation_id"])
    op.create_index("ix_sales_invoices_sales_order_id", "sales_invoices", ["sales_order_id"])

    op.create_table(
        "sales_quotations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("quotation_number", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("converted_order_id", sa.String(length=36), nullable=True),
        sa.Column("converted_invoice_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "quotation_number"),
    )
    op.create_index("ix_sales_quotations_tenant_id", "sales_quotations", ["tenant_id"])
    op.create_index("ix_sales_quotations_status", "sales_quotations", ["status"])
    op.create_index("ix_sales_quotations_quotation_number", "sales_quotations", ["quotation_number"])

    op.create_table(
        "sales_quotation_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("quotation_id", sa.String(length=36), sa.ForeignKey("sales_quotations.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_sales_quotation_items_tenant_id", "sales_quotation_items", ["tenant_id"])
    op.create_index("ix_sales_quotation_items_quotation_id", "sales_quotation_items", ["quotation_id"])

    op.create_table(
        "sales_orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_number", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("quotation_id", sa.String(length=36), sa.ForeignKey("sales_quotations.id"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("converted_invoice_id", sa.String(length=36), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "order_number"),
    )
    op.create_index("ix_sales_orders_tenant_id", "sales_orders", ["tenant_id"])
    op.create_index("ix_sales_orders_status", "sales_orders", ["status"])
    op.create_index("ix_sales_orders_order_number", "sales_orders", ["order_number"])

    op.create_table(
        "sales_order_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("sales_order_id", sa.String(length=36), sa.ForeignKey("sales_orders.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_sales_order_items_tenant_id", "sales_order_items", ["tenant_id"])
    op.create_index("ix_sales_order_items_sales_order_id", "sales_order_items", ["sales_order_id"])

    op.create_table(
        "sales_returns",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("return_number", sa.String(length=50), nullable=False),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("sales_invoice_id", sa.String(length=36), sa.ForeignKey("sales_invoices.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("reason", sa.String(length=80), nullable=False, server_default="other"),
        sa.Column("restock", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "return_number"),
    )
    op.create_index("ix_sales_returns_tenant_id", "sales_returns", ["tenant_id"])
    op.create_index("ix_sales_returns_status", "sales_returns", ["status"])
    op.create_index("ix_sales_returns_return_number", "sales_returns", ["return_number"])

    op.create_table(
        "sales_return_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("sales_return_id", sa.String(length=36), sa.ForeignKey("sales_returns.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("condition", sa.String(length=40), nullable=False, server_default="sellable"),
    )
    op.create_index("ix_sales_return_items_tenant_id", "sales_return_items", ["tenant_id"])
    op.create_index("ix_sales_return_items_sales_return_id", "sales_return_items", ["sales_return_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_return_items_sales_return_id", table_name="sales_return_items")
    op.drop_index("ix_sales_return_items_tenant_id", table_name="sales_return_items")
    op.drop_table("sales_return_items")
    op.drop_index("ix_sales_returns_return_number", table_name="sales_returns")
    op.drop_index("ix_sales_returns_status", table_name="sales_returns")
    op.drop_index("ix_sales_returns_tenant_id", table_name="sales_returns")
    op.drop_table("sales_returns")
    op.drop_index("ix_sales_order_items_sales_order_id", table_name="sales_order_items")
    op.drop_index("ix_sales_order_items_tenant_id", table_name="sales_order_items")
    op.drop_table("sales_order_items")
    op.drop_index("ix_sales_orders_order_number", table_name="sales_orders")
    op.drop_index("ix_sales_orders_status", table_name="sales_orders")
    op.drop_index("ix_sales_orders_tenant_id", table_name="sales_orders")
    op.drop_table("sales_orders")
    op.drop_index("ix_sales_quotation_items_quotation_id", table_name="sales_quotation_items")
    op.drop_index("ix_sales_quotation_items_tenant_id", table_name="sales_quotation_items")
    op.drop_table("sales_quotation_items")
    op.drop_index("ix_sales_quotations_quotation_number", table_name="sales_quotations")
    op.drop_index("ix_sales_quotations_status", table_name="sales_quotations")
    op.drop_index("ix_sales_quotations_tenant_id", table_name="sales_quotations")
    op.drop_table("sales_quotations")
    op.drop_index("ix_sales_invoices_sales_order_id", table_name="sales_invoices")
    op.drop_index("ix_sales_invoices_quotation_id", table_name="sales_invoices")
    op.drop_column("sales_invoices", "sales_order_id")
    op.drop_column("sales_invoices", "quotation_id")
