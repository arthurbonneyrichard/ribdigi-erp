"""Hotel folio → sales invoice link for checkout settlement.

Revision ID: 20260920_0113
Revises: 20260920_0112
Create Date: 2026-09-20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260920_0113"
down_revision = "20260920_0112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hotel_folios",
        sa.Column(
            "sales_invoice_id",
            sa.String(length=36),
            sa.ForeignKey("sales_invoices.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_hotel_folios_sales_invoice_id", "hotel_folios", ["sales_invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_hotel_folios_sales_invoice_id", table_name="hotel_folios")
    op.drop_column("hotel_folios", "sales_invoice_id")
