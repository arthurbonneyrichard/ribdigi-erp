"""Add purchase_order_items.discount for line discounts (BR-6.3).

Revision ID: 20260814_0096
Revises: 20260814_0095
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0096"
down_revision = "20260814_0095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_order_items",
        sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("purchase_order_items", "discount")
