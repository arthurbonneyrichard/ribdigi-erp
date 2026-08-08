"""multi-store transfers and warehouse stock

Revision ID: 20260808_0008
Revises: 20260808_0007
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0008"
down_revision = "20260808_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stores", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column("stores", sa.Column("phone", sa.String(length=50), nullable=True))
    op.add_column("stores", sa.Column("manager_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True))

    op.create_table(
        "warehouse_stocks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.UniqueConstraint("tenant_id", "warehouse_id", "product_id"),
    )
    op.create_index("ix_warehouse_stocks_warehouse", "warehouse_stocks", ["warehouse_id"])
    op.create_index("ix_warehouse_stocks_product", "warehouse_stocks", ["product_id"])

    op.create_table(
        "stock_transfers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("transfer_number", sa.String(length=50), nullable=False),
        sa.Column("from_store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("to_store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("from_warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("to_warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("shipped_by", sa.String(length=36), nullable=True),
        sa.Column("received_by", sa.String(length=36), nullable=True),
        sa.Column("shipped_at", sa.DateTime(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "transfer_number"),
    )
    op.create_index("ix_stock_transfers_tenant", "stock_transfers", ["tenant_id"])
    op.create_index("ix_stock_transfers_status", "stock_transfers", ["status"])

    op.create_table(
        "stock_transfer_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("transfer_id", sa.String(length=36), sa.ForeignKey("stock_transfers.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("shipped_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("received_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
    )
    op.create_index("ix_stock_transfer_items_transfer", "stock_transfer_items", ["transfer_id"])


def downgrade() -> None:
    op.drop_table("stock_transfer_items")
    op.drop_table("stock_transfers")
    op.drop_table("warehouse_stocks")
    op.drop_column("stores", "manager_id")
    op.drop_column("stores", "phone")
    op.drop_column("stores", "address")
