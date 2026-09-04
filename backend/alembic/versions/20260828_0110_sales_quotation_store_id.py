"""Optional sales_quotations.store_id for store-manager scope.

Revision ID: 20260828_0110
Revises: 20260823_0109
Create Date: 2026-08-28

Nullable FK — ADR-005 native user↔store membership still deferred.
Backfill from converted order/invoice store where available.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260828_0110"
down_revision = "20260823_0109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_quotations",
        sa.Column(
            "store_id",
            sa.String(length=36),
            sa.ForeignKey("stores.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_sales_quotations_store_id",
        "sales_quotations",
        ["store_id"],
    )
    op.execute(
        """
        UPDATE sales_quotations sq
        SET store_id = so.store_id
        FROM sales_orders so
        WHERE sq.converted_order_id = so.id
          AND sq.store_id IS NULL
          AND so.store_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE sales_quotations sq
        SET store_id = si.store_id
        FROM sales_invoices si
        WHERE sq.converted_invoice_id = si.id
          AND sq.store_id IS NULL
          AND si.store_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_sales_quotations_store_id", table_name="sales_quotations")
    op.drop_column("sales_quotations", "store_id")
