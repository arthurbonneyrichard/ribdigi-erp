"""Add line_tax breakdown on sales invoice items (BR-12.2).

Revision ID: 20260813_0093
Revises: 20260813_0092
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0093"
down_revision = "20260813_0092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_invoice_items",
        sa.Column("line_tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "sales_invoice_items",
        sa.Column("is_reverse_charge", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "sales_invoice_items",
        sa.Column("tax_components", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_invoice_items", "tax_components")
    op.drop_column("sales_invoice_items", "is_reverse_charge")
    op.drop_column("sales_invoice_items", "line_tax")
