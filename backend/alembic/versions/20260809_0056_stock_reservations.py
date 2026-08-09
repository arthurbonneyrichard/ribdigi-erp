"""Sales order soft allocation (stock reservations)

Revision ID: 20260809_0056
Revises: 20260809_0055
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0056"
down_revision = "20260809_0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("reserved_qty", sa.Numeric(14, 3), nullable=False, server_default="0"))
    with op.batch_alter_table("warehouse_stocks") as batch:
        batch.add_column(sa.Column("reserved_qty", sa.Numeric(14, 3), nullable=False, server_default="0"))
    with op.batch_alter_table("sales_orders") as batch:
        batch.add_column(sa.Column("store_id", sa.String(length=36), nullable=True))
        batch.add_column(sa.Column("warehouse_id", sa.String(length=36), nullable=True))
        batch.create_foreign_key("fk_sales_orders_store_id", "stores", ["store_id"], ["id"])
        batch.create_foreign_key("fk_sales_orders_warehouse_id", "warehouses", ["warehouse_id"], ["id"])
        batch.create_index("ix_sales_orders_store_id", ["store_id"])
        batch.create_index("ix_sales_orders_warehouse_id", ["warehouse_id"])

    op.create_table(
        "stock_reservations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("variant_id", sa.String(length=36), sa.ForeignKey("product_variants.id"), nullable=True, index=True),
        sa.Column("warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=True, index=True),
        sa.Column(
            "sales_order_id",
            sa.String(length=36),
            sa.ForeignKey("sales_orders.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "sales_order_item_id",
            sa.String(length=36),
            sa.ForeignKey("sales_order_items.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active", index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_stock_reservations_tenant_product_status",
        "stock_reservations",
        ["tenant_id", "product_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_stock_reservations_tenant_product_status", table_name="stock_reservations")
    op.drop_table("stock_reservations")
    with op.batch_alter_table("sales_orders") as batch:
        batch.drop_index("ix_sales_orders_warehouse_id")
        batch.drop_index("ix_sales_orders_store_id")
        batch.drop_constraint("fk_sales_orders_warehouse_id", type_="foreignkey")
        batch.drop_constraint("fk_sales_orders_store_id", type_="foreignkey")
        batch.drop_column("warehouse_id")
        batch.drop_column("store_id")
    with op.batch_alter_table("warehouse_stocks") as batch:
        batch.drop_column("reserved_qty")
    with op.batch_alter_table("products") as batch:
        batch.drop_column("reserved_qty")
