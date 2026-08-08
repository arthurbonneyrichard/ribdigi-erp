"""purchase invoices

Revision ID: 20260808_0017
Revises: 20260808_0016
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0017"
down_revision = "20260808_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_invoices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("invoice_number", sa.String(length=50), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("purchase_order_id", sa.String(length=36), sa.ForeignKey("purchase_orders.id"), nullable=True),
        sa.Column("goods_receipt_id", sa.String(length=36), sa.ForeignKey("goods_receipts.id"), nullable=True),
        sa.Column("supplier_invoice_number", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("invoice_date", sa.DateTime(), nullable=False),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("ap_posted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attachment_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "invoice_number"),
    )
    op.create_index("ix_purchase_invoices_tenant_id", "purchase_invoices", ["tenant_id"])
    op.create_index("ix_purchase_invoices_invoice_number", "purchase_invoices", ["invoice_number"])
    op.create_index("ix_purchase_invoices_status", "purchase_invoices", ["status"])
    op.create_index("ix_purchase_invoices_purchase_order_id", "purchase_invoices", ["purchase_order_id"])
    op.create_index("ix_purchase_invoices_goods_receipt_id", "purchase_invoices", ["goods_receipt_id"])

    op.create_table(
        "purchase_invoice_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "purchase_invoice_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_invoices.id"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_purchase_invoice_items_tenant_id", "purchase_invoice_items", ["tenant_id"])
    op.create_index(
        "ix_purchase_invoice_items_purchase_invoice_id",
        "purchase_invoice_items",
        ["purchase_invoice_id"],
    )

    op.add_column(
        "supplier_payments",
        sa.Column(
            "purchase_invoice_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_invoices.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_supplier_payments_purchase_invoice_id", "supplier_payments", ["purchase_invoice_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_supplier_payments_purchase_invoice_id", table_name="supplier_payments")
    op.drop_column("supplier_payments", "purchase_invoice_id")
    op.drop_index("ix_purchase_invoice_items_purchase_invoice_id", table_name="purchase_invoice_items")
    op.drop_index("ix_purchase_invoice_items_tenant_id", table_name="purchase_invoice_items")
    op.drop_table("purchase_invoice_items")
    op.drop_index("ix_purchase_invoices_goods_receipt_id", table_name="purchase_invoices")
    op.drop_index("ix_purchase_invoices_purchase_order_id", table_name="purchase_invoices")
    op.drop_index("ix_purchase_invoices_status", table_name="purchase_invoices")
    op.drop_index("ix_purchase_invoices_invoice_number", table_name="purchase_invoices")
    op.drop_index("ix_purchase_invoices_tenant_id", table_name="purchase_invoices")
    op.drop_table("purchase_invoices")
