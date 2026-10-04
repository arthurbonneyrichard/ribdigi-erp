"""Product category tax_rate_id for category-specific tax (BR-12.1 / BR-2.8).

Revision ID: 20260812_0077
Revises: 20260812_0076
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0077"
down_revision = "20260812_0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_categories",
        sa.Column("tax_rate_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_product_categories_tax_rate_id",
        "product_categories",
        "tax_rates",
        ["tax_rate_id"],
        ["id"],
    )
    op.create_index(
        "ix_product_categories_tax_rate_id",
        "product_categories",
        ["tax_rate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_categories_tax_rate_id", table_name="product_categories")
    op.drop_constraint(
        "fk_product_categories_tax_rate_id", "product_categories", type_="foreignkey"
    )
    op.drop_column("product_categories", "tax_rate_id")
