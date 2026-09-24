"""sales order fulfillment timestamps

Revision ID: 20260812_0057
Revises: 20260812_0056
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0057"
down_revision = "20260812_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_orders", sa.Column("processing_at", sa.DateTime(), nullable=True))
    op.add_column("sales_orders", sa.Column("shipped_at", sa.DateTime(), nullable=True))
    op.add_column("sales_orders", sa.Column("delivered_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("sales_orders", "delivered_at")
    op.drop_column("sales_orders", "shipped_at")
    op.drop_column("sales_orders", "processing_at")
