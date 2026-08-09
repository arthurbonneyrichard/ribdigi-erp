"""Sales order delivery fields and logistics timestamps

Revision ID: 20260809_0057
Revises: 20260809_0056
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0057"
down_revision = "20260809_0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sales_orders") as batch:
        batch.add_column(sa.Column("delivery_date", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("delivery_address", sa.Text(), nullable=True))
        batch.add_column(sa.Column("processing_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("shipped_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("delivered_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sales_orders") as batch:
        batch.drop_column("delivered_at")
        batch.drop_column("shipped_at")
        batch.drop_column("processing_at")
        batch.drop_column("delivery_address")
        batch.drop_column("delivery_date")
