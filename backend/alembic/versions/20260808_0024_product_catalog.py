"""product catalog categories brands units images

Revision ID: 20260808_0024
Revises: 20260808_0023
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0024"
down_revision = "20260808_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("parent_id", sa.String(length=36), sa.ForeignKey("product_categories.id"), nullable=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "code"),
    )
    op.create_index("ix_product_categories_tenant_id", "product_categories", ["tenant_id"])
    op.create_index("ix_product_categories_parent_id", "product_categories", ["parent_id"])

    op.create_table(
        "brands",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "code"),
    )
    op.create_index("ix_brands_tenant_id", "brands", ["tenant_id"])

    op.create_table(
        "units_of_measure",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "code"),
    )
    op.create_index("ix_units_of_measure_tenant_id", "units_of_measure", ["tenant_id"])

    op.add_column(
        "products",
        sa.Column("category_id", sa.String(length=36), sa.ForeignKey("product_categories.id"), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("brand_id", sa.String(length=36), sa.ForeignKey("brands.id"), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("unit_id", sa.String(length=36), sa.ForeignKey("units_of_measure.id"), nullable=True),
    )
    op.add_column("products", sa.Column("image_url", sa.String(length=500), nullable=True))
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_brand_id", "products", ["brand_id"])
    op.create_index("ix_products_unit_id", "products", ["unit_id"])


def downgrade() -> None:
    op.drop_index("ix_products_unit_id", table_name="products")
    op.drop_index("ix_products_brand_id", table_name="products")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_column("products", "image_url")
    op.drop_column("products", "unit_id")
    op.drop_column("products", "brand_id")
    op.drop_column("products", "category_id")
    op.drop_index("ix_units_of_measure_tenant_id", table_name="units_of_measure")
    op.drop_table("units_of_measure")
    op.drop_index("ix_brands_tenant_id", table_name="brands")
    op.drop_table("brands")
    op.drop_index("ix_product_categories_parent_id", table_name="product_categories")
    op.drop_index("ix_product_categories_tenant_id", table_name="product_categories")
    op.drop_table("product_categories")
