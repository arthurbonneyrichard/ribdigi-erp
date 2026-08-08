"""sales line variant_id

Revision ID: 20260808_0020
Revises: 20260808_0019
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0020"
down_revision = "20260808_0019"
branch_labels = None
depends_on = None

_TABLES = (
    "sales_invoice_items",
    "sales_quotation_items",
    "sales_order_items",
    "sales_return_items",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "variant_id",
                sa.String(length=36),
                sa.ForeignKey("product_variants.id"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_variant_id", table, ["variant_id"])


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_variant_id", table_name=table)
        op.drop_column(table, "variant_id")
