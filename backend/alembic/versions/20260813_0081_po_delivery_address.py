"""Add delivery_address to purchase orders (BR-6.3).

Revision ID: 20260813_0081
Revises: 20260813_0080
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0081"
down_revision = "20260813_0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_orders",
        sa.Column("delivery_address", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("purchase_orders", "delivery_address")
