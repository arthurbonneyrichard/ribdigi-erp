"""GRN item batch and expiry fields

Revision ID: 20260809_0048
Revises: 20260809_0047
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0048"
down_revision = "20260809_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "goods_receipt_items",
        sa.Column("batch_id", sa.String(length=36), sa.ForeignKey("product_batches.id"), nullable=True),
    )
    op.add_column("goods_receipt_items", sa.Column("batch_number", sa.String(length=80), nullable=True))
    op.add_column("goods_receipt_items", sa.Column("manufacturing_date", sa.DateTime(), nullable=True))
    op.add_column("goods_receipt_items", sa.Column("expiry_date", sa.DateTime(), nullable=True))
    op.create_index("ix_goods_receipt_items_batch_id", "goods_receipt_items", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_goods_receipt_items_batch_id", table_name="goods_receipt_items")
    op.drop_column("goods_receipt_items", "expiry_date")
    op.drop_column("goods_receipt_items", "manufacturing_date")
    op.drop_column("goods_receipt_items", "batch_number")
    op.drop_column("goods_receipt_items", "batch_id")
