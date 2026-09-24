"""Add line_tax breakdown on purchase invoice items (BR-12.2).

Revision ID: 20260813_0094
Revises: 20260813_0093
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0094"
down_revision = "20260813_0093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_invoice_items",
        sa.Column("line_subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "purchase_invoice_items",
        sa.Column("line_tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "purchase_invoice_items",
        sa.Column("tax_components", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("purchase_invoice_items", "tax_components")
    op.drop_column("purchase_invoice_items", "line_tax")
    op.drop_column("purchase_invoice_items", "line_subtotal")
