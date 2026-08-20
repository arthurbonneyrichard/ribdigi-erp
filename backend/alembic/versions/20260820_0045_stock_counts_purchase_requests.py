"""physical stock counts and purchase requests

Revision ID: 20260820_0045
Revises: 20260808_0044
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = "20260820_0045"
down_revision = "20260808_0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_counts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("count_number", sa.String(length=50), nullable=False),
        sa.Column("warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("counted_by", sa.String(length=36), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "count_number"),
    )
    op.create_index("ix_stock_counts_tenant", "stock_counts", ["tenant_id"])
    op.create_index("ix_stock_counts_warehouse", "stock_counts", ["warehouse_id"])
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
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "variant_id",
            sa.String(length=36),
            sa.ForeignKey("product_variants.id"),
            nullable=True,
        ),
        sa.Column("expected_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("actual_qty", sa.Numeric(14, 3), nullable=True),
        sa.Column("difference", sa.Numeric(14, 3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("stock_count_id", "product_id", "variant_id"),
    )
    op.create_index("ix_stock_count_items_count", "stock_count_items", ["stock_count_id"])
    op.create_index("ix_stock_count_items_product", "stock_count_items", ["product_id"])

    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("request_number", sa.String(length=50), nullable=False),
        sa.Column("request_date", sa.DateTime(), nullable=False),
        sa.Column("required_date", sa.DateTime(), nullable=True),
        sa.Column("warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("converted_po_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "request_number"),
    )
    op.create_index("ix_purchase_requests_tenant", "purchase_requests", ["tenant_id"])
    op.create_index("ix_purchase_requests_status", "purchase_requests", ["status"])

    op.create_table(
        "purchase_request_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "purchase_request_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_requests.id"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "variant_id",
            sa.String(length=36),
            sa.ForeignKey("product_variants.id"),
            nullable=True,
        ),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_purchase_request_items_request",
        "purchase_request_items",
        ["purchase_request_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_request_items_request", table_name="purchase_request_items")
    op.drop_table("purchase_request_items")
    op.drop_index("ix_purchase_requests_status", table_name="purchase_requests")
    op.drop_index("ix_purchase_requests_tenant", table_name="purchase_requests")
    op.drop_table("purchase_requests")
    op.drop_index("ix_stock_count_items_product", table_name="stock_count_items")
    op.drop_index("ix_stock_count_items_count", table_name="stock_count_items")
    op.drop_table("stock_count_items")
    op.drop_index("ix_stock_counts_status", table_name="stock_counts")
    op.drop_index("ix_stock_counts_warehouse", table_name="stock_counts")
    op.drop_index("ix_stock_counts_tenant", table_name="stock_counts")
    op.drop_table("stock_counts")
