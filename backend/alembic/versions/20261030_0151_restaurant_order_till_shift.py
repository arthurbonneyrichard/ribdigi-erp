"""Restaurant orders remember the till shift that took the money.

Revision ID: 20261030_0151
Revises: 20261030_0150
Create Date: 2026-10-30

The restaurant till rings restaurant orders, so a paid order points at the
restaurant till shift (cash drawer) that took it. The walk-up receipt, payment
and return tables from 20261030_0150 are not needed and are dropped (they never
held rows). Shifts and cash moves stay.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261030_0151"
down_revision = "20261030_0150"
branch_labels = None
depends_on = None

# Children before parents.
UNUSED = (
    "restaurant_till_return_lines",
    "restaurant_till_returns",
    "restaurant_till_payments",
    "restaurant_till_receipt_lines",
    "restaurant_till_receipts",
)


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in _inspector().get_columns(table)}


def upgrade() -> None:
    for name in UNUSED:
        if _inspector().has_table(name):
            op.drop_table(name)
    if not _has_column("restaurant_orders", "till_shift_id"):
        with op.batch_alter_table("restaurant_orders") as batch:
            batch.add_column(sa.Column("till_shift_id", sa.String(length=36), nullable=True))
            batch.create_foreign_key(
                "fk_restaurant_orders_till_shift_id",
                "restaurant_till_shifts",
                ["till_shift_id"],
                ["id"],
            )
            batch.create_index("ix_restaurant_orders_till_shift_id", ["till_shift_id"])


def downgrade() -> None:
    if _has_column("restaurant_orders", "till_shift_id"):
        with op.batch_alter_table("restaurant_orders") as batch:
            batch.drop_index("ix_restaurant_orders_till_shift_id")
            batch.drop_constraint("fk_restaurant_orders_till_shift_id", type_="foreignkey")
            batch.drop_column("till_shift_id")
    # The dropped tables were never used; 20261030_0150's downgrade skips missing tables.
