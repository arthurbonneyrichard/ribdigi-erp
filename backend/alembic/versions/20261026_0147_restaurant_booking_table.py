"""Name the table when a restaurant booking is seated.

Revision ID: 20261026_0147
Revises: 20261026_0146
Create Date: 2026-10-26

Seating a guest request can store the table. It does not open an order and
does not take a payment. Skipped when the column already exists. Do not
apply this to live ribdigi_erp from this change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261026_0147"
down_revision = "20261026_0146"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "restaurant_bookings", "table_id"):
        return
    if not sa.inspect(bind).has_table("restaurant_bookings"):
        return
    op.add_column(
        "restaurant_bookings",
        sa.Column("table_id", sa.String(length=36), sa.ForeignKey("restaurant_tables.id"), nullable=True),
    )
    op.create_index("ix_restaurant_bookings_table_id", "restaurant_bookings", ["table_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "restaurant_bookings", "table_id"):
        return
    op.drop_index("ix_restaurant_bookings_table_id", table_name="restaurant_bookings")
    op.drop_column("restaurant_bookings", "table_id")
