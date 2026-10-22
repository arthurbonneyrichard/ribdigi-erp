"""Purchase invoice receive location (store / warehouse) for posted manual bills.

Revision ID: 20260930_0128
Revises: 20260930_0127

Renumbered after sibling 0127 offline POS auth so the chain stays linear.
Manual supplier bills already use purchase_invoice_items (one header, many lines).
Posted manual bills receive stock at the selected warehouse; persist that location
on the header. Idempotent ADD COLUMN so a partial apply is a no-op.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260930_0128"
down_revision = "20260930_0127"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    cols = _column_names("purchase_invoices")
    if "warehouse_id" not in cols:
        op.add_column(
            "purchase_invoices",
            sa.Column(
                "warehouse_id",
                sa.String(length=36),
                sa.ForeignKey("warehouses.id"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_purchase_invoices_warehouse_id",
            "purchase_invoices",
            ["warehouse_id"],
        )
    if "store_id" not in cols:
        op.add_column(
            "purchase_invoices",
            sa.Column(
                "store_id",
                sa.String(length=36),
                sa.ForeignKey("stores.id"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_purchase_invoices_store_id",
            "purchase_invoices",
            ["store_id"],
        )
    item_cols = _column_names("purchase_invoice_items")
    if "line_no" not in item_cols:
        op.add_column(
            "purchase_invoice_items",
            sa.Column("line_no", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    item_cols = _column_names("purchase_invoice_items")
    if "line_no" in item_cols:
        op.drop_column("purchase_invoice_items", "line_no")
    cols = _column_names("purchase_invoices")
    if "store_id" in cols:
        op.drop_index("ix_purchase_invoices_store_id", table_name="purchase_invoices")
        op.drop_column("purchase_invoices", "store_id")
    if "warehouse_id" in cols:
        op.drop_index("ix_purchase_invoices_warehouse_id", table_name="purchase_invoices")
        op.drop_column("purchase_invoices", "warehouse_id")
