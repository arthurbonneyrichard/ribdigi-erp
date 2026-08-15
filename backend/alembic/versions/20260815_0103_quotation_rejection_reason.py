"""Add sales_quotations.rejection_reason for quotation Reject honesty (BR-7.2).

Revision ID: 20260815_0103
Revises: 20260815_0102
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa


revision = "20260815_0103"
down_revision = "20260815_0102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_quotations",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_quotations", "rejection_reason")
