"""sales order soft reservation + delivery fields

Revision ID: 20260812_0056
Revises: 20260812_0055
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0056"
down_revision = "20260812_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_orders", sa.Column("store_id", sa.String(length=36), nullable=True))
    op.add_column("sales_orders", sa.Column("delivery_date", sa.DateTime(), nullable=True))
    op.add_column("sales_orders", sa.Column("delivery_address", sa.Text(), nullable=True))
    op.create_index("ix_sales_orders_store_id", "sales_orders", ["store_id"])

    op.create_table(
        "stock_reservations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("sales_order_id", sa.String(length=36), nullable=False),
        sa.Column("sales_order_item_id", sa.String(length=36), nullable=True),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("variant_id", sa.String(length=36), nullable=True),
        sa.Column("warehouse_id", sa.String(length=36), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["sales_order_id"], ["sales_orders.id"]),
        sa.ForeignKeyConstraint(["sales_order_item_id"], ["sales_order_items.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
    )
    op.create_index("ix_stock_reservations_tenant_id", "stock_reservations", ["tenant_id"])
    op.create_index("ix_stock_reservations_sales_order_id", "stock_reservations", ["sales_order_id"])
    op.create_index("ix_stock_reservations_product_id", "stock_reservations", ["product_id"])
    op.create_index("ix_stock_reservations_warehouse_id", "stock_reservations", ["warehouse_id"])
    op.create_index("ix_stock_reservations_status", "stock_reservations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_stock_reservations_status", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_warehouse_id", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_product_id", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_sales_order_id", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_tenant_id", table_name="stock_reservations")
    op.drop_table("stock_reservations")
    op.drop_index("ix_sales_orders_store_id", table_name="sales_orders")
    op.drop_column("sales_orders", "delivery_address")
    op.drop_column("sales_orders", "delivery_date")
    op.drop_column("sales_orders", "store_id")
