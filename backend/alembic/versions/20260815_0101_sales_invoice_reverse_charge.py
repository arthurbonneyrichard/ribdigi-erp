"""Add sales_invoices.is_reverse_charge header flag (BR-12.2 parity).

Revision ID: 20260815_0101
Revises: 20260814_0100
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa


revision = "20260815_0101"
down_revision = "20260814_0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_invoices",
        sa.Column("is_reverse_charge", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("sales_invoices", "is_reverse_charge")
