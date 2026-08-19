"""PO delivery address and line discount

Revision ID: 20260809_0060
Revises: 20260809_0059
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0060"
down_revision = "20260809_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("purchase_orders") as batch:
        batch.add_column(sa.Column("delivery_address", sa.Text(), nullable=True))
    with op.batch_alter_table("purchase_order_items") as batch:
        batch.add_column(
            sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("purchase_order_items") as batch:
        batch.drop_column("discount")
    with op.batch_alter_table("purchase_orders") as batch:
        batch.drop_column("delivery_address")
