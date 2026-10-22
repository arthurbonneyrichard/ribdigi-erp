"""Product / warehouse low-stock floor (minimum_stock).

Revision ID: 20260928_0122
Revises: 20260928_0121

Sibling collision: this used to share revision id 20260928_0122 with coupon
migrations. Unique id after hotel 0121. Idempotent IF NOT EXISTS.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260928_0122"
down_revision = "20260928_0121"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    product_cols = _column_names("products")
    if "minimum_stock" not in product_cols:
        op.add_column(
            "products",
            sa.Column("minimum_stock", sa.Numeric(14, 3), nullable=False, server_default="0"),
        )
    stock_cols = _column_names("warehouse_stocks")
    if "minimum_stock" not in stock_cols:
        op.add_column(
            "warehouse_stocks",
            sa.Column("minimum_stock", sa.Numeric(14, 3), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    return
