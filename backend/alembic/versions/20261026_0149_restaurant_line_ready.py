"""Kitchen item ready on a restaurant order line.

Revision ID: 20261026_0149
Revises: 20261026_0148
Create Date: 2026-10-26

A cook can mark one item ready without closing the order. Existing lines
start as queued. Skipped when the column already exists. Do not apply this
to live ribdigi_erp from this change.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261026_0149"
down_revision = "20261026_0148"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if _has_column(bind, "restaurant_order_lines", "prep_status"):
        return
    if not sa.inspect(bind).has_table("restaurant_order_lines"):
        return
    op.add_column(
        "restaurant_order_lines",
        sa.Column("prep_status", sa.String(length=20), nullable=False, server_default="queued"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "restaurant_order_lines", "prep_status"):
        return
    op.drop_column("restaurant_order_lines", "prep_status")
