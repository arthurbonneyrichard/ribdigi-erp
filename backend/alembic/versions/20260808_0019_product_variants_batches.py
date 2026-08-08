"""product variants and batches

Revision ID: 20260808_0019
Revises: 20260808_0018
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0019"
down_revision = "20260808_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("tracks_batches", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "product_variants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("barcode", sa.String(length=100), nullable=True),
        sa.Column("size", sa.String(length=80), nullable=True),
        sa.Column("color", sa.String(length=80), nullable=True),
        sa.Column("flavor", sa.String(length=80), nullable=True),
        sa.Column("cost_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("selling_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("stock_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "sku"),
    )
    op.create_index("ix_product_variants_tenant_id", "product_variants", ["tenant_id"])
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])
    op.create_index("ix_product_variants_sku", "product_variants", ["sku"])
    op.create_index("ix_product_variants_barcode", "product_variants", ["barcode"])

    op.create_table(
        "product_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "variant_id",
            sa.String(length=36),
            sa.ForeignKey("product_variants.id"),
            nullable=True,
        ),
        sa.Column("warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("batch_number", sa.String(length=80), nullable=False),
        sa.Column("manufacturing_date", sa.DateTime(), nullable=True),
        sa.Column("expiry_date", sa.DateTime(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "product_id", "batch_number", "variant_id"),
    )
    op.create_index("ix_product_batches_tenant_id", "product_batches", ["tenant_id"])
    op.create_index("ix_product_batches_product_id", "product_batches", ["product_id"])
    op.create_index("ix_product_batches_variant_id", "product_batches", ["variant_id"])
    op.create_index("ix_product_batches_batch_number", "product_batches", ["batch_number"])
    op.create_index("ix_product_batches_expiry_date", "product_batches", ["expiry_date"])

    op.add_column(
        "stock_movements",
        sa.Column("variant_id", sa.String(length=36), sa.ForeignKey("product_variants.id"), nullable=True),
    )
    op.add_column(
        "stock_movements",
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey("product_batches.id"), nullable=True),
    )
    op.create_index("ix_stock_movements_variant_id", "stock_movements", ["variant_id"])
    op.create_index("ix_stock_movements_batch_id", "stock_movements", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_movements_batch_id", table_name="stock_movements")
    op.drop_index("ix_stock_movements_variant_id", table_name="stock_movements")
    op.drop_column("stock_movements", "batch_id")
    op.drop_column("stock_movements", "variant_id")
    op.drop_index("ix_product_batches_expiry_date", table_name="product_batches")
    op.drop_index("ix_product_batches_batch_number", table_name="product_batches")
    op.drop_index("ix_product_batches_variant_id", table_name="product_batches")
    op.drop_index("ix_product_batches_product_id", table_name="product_batches")
    op.drop_index("ix_product_batches_tenant_id", table_name="product_batches")
    op.drop_table("product_batches")
    op.drop_index("ix_product_variants_barcode", table_name="product_variants")
    op.drop_index("ix_product_variants_sku", table_name="product_variants")
    op.drop_index("ix_product_variants_product_id", table_name="product_variants")
    op.drop_index("ix_product_variants_tenant_id", table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_column("products", "tracks_batches")
