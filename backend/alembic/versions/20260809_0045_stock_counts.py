"""Physical stock count sessions

Revision ID: 20260809_0045
Revises: 20260808_0044
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0045"
down_revision = "20260808_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_counts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=False
        ),
        sa.Column("count_number", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("completed_by", sa.String(length=36), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "count_number"),
    )
    op.create_index("ix_stock_counts_tenant_id", "stock_counts", ["tenant_id"])
    op.create_index("ix_stock_counts_warehouse_id", "stock_counts", ["warehouse_id"])
    op.create_index("ix_stock_counts_count_number", "stock_counts", ["count_number"])
    op.create_index("ix_stock_counts_status", "stock_counts", ["status"])

    op.create_table(
        "stock_count_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "stock_count_id",
            sa.String(length=36),
            sa.ForeignKey("stock_counts.id"),
            nullable=False,
        ),
        sa.Column(
            "product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False
        ),
        sa.Column("expected_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("counted_qty", sa.Numeric(14, 3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "stock_count_id", "product_id"),
    )
    op.create_index("ix_stock_count_items_tenant_id", "stock_count_items", ["tenant_id"])
    op.create_index("ix_stock_count_items_stock_count_id", "stock_count_items", ["stock_count_id"])
    op.create_index("ix_stock_count_items_product_id", "stock_count_items", ["product_id"])


def downgrade() -> None:
    op.drop_table("stock_count_items")
    op.drop_table("stock_counts")
