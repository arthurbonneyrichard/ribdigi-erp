"""Persist sale discount type and percent on invoices, quotations, and orders.

Revision ID: 20260928_0118
Revises: 20260928_0117
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260928_0118"
down_revision = "20260928_0117"
branch_labels = None
depends_on = None

TABLES_HEADER = (
    "sales_invoices",
    "sales_quotations",
    "sales_orders",
)
TABLES_LINE = (
    "sales_invoice_items",
    "sales_quotation_items",
    "sales_order_items",
)


def upgrade() -> None:
    for table in TABLES_HEADER:
        op.add_column(table, sa.Column("discount_type", sa.String(length=16), nullable=False, server_default="fixed"))
        op.add_column(table, sa.Column("discount_percent", sa.Numeric(7, 4), nullable=False, server_default="0"))
    for table in TABLES_LINE:
        op.add_column(table, sa.Column("discount_type", sa.String(length=16), nullable=False, server_default="fixed"))
        op.add_column(table, sa.Column("discount_percent", sa.Numeric(7, 4), nullable=False, server_default="0"))


def downgrade() -> None:
    for table in TABLES_LINE:
        op.drop_column(table, "discount_percent")
        op.drop_column(table, "discount_type")
    for table in TABLES_HEADER:
        op.drop_column(table, "discount_percent")
        op.drop_column(table, "discount_type")
