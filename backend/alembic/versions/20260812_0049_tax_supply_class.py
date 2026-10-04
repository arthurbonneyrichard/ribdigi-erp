"""Product and invoice line tax supply class

Revision ID: 20260812_0049
Revises: 20260812_0048
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0049"
down_revision = "20260812_0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("tax_supply_class", sa.String(length=20), nullable=False, server_default="standard"),
    )
    op.add_column(
        "sales_invoice_items",
        sa.Column("tax_supply_class", sa.String(length=20), nullable=False, server_default="standard"),
    )
    op.add_column(
        "sales_invoice_items",
        sa.Column("line_subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    # Backfill exempt products
    op.execute(
        "UPDATE products SET tax_supply_class = 'exempt' WHERE tax_exempt IS true"
    )


def downgrade() -> None:
    op.drop_column("sales_invoice_items", "line_subtotal")
    op.drop_column("sales_invoice_items", "tax_supply_class")
    op.drop_column("products", "tax_supply_class")
