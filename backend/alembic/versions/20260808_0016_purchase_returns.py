"""purchase returns / debit notes

Revision ID: 20260808_0016
Revises: 20260808_0015
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0016"
down_revision = "20260808_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_returns",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("return_number", sa.String(length=50), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("purchase_order_id", sa.String(length=36), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("goods_receipt_id", sa.String(length=36), sa.ForeignKey("goods_receipts.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("reason", sa.String(length=80), nullable=False, server_default="other"),
        sa.Column("debit_note_number", sa.String(length=50), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("posted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "return_number"),
    )
    op.create_index("ix_purchase_returns_tenant_id", "purchase_returns", ["tenant_id"])
    op.create_index("ix_purchase_returns_status", "purchase_returns", ["status"])
    op.create_index("ix_purchase_returns_return_number", "purchase_returns", ["return_number"])

    op.create_table(
        "purchase_return_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "purchase_return_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_returns.id"),
            nullable=False,
        ),
        sa.Column(
            "goods_receipt_item_id",
            sa.String(length=36),
            sa.ForeignKey("goods_receipt_items.id"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_purchase_return_items_tenant_id", "purchase_return_items", ["tenant_id"])
    op.create_index(
        "ix_purchase_return_items_purchase_return_id", "purchase_return_items", ["purchase_return_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_return_items_purchase_return_id", table_name="purchase_return_items")
    op.drop_index("ix_purchase_return_items_tenant_id", table_name="purchase_return_items")
    op.drop_table("purchase_return_items")
    op.drop_index("ix_purchase_returns_return_number", table_name="purchase_returns")
    op.drop_index("ix_purchase_returns_status", table_name="purchase_returns")
    op.drop_index("ix_purchase_returns_tenant_id", table_name="purchase_returns")
    op.drop_table("purchase_returns")
