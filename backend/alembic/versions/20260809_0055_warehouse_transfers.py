"""Allow warehouse-only stock transfers (nullable store FKs)

Revision ID: 20260809_0055
Revises: 20260809_0054
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0055"
down_revision = "20260809_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stock_transfers") as batch:
        batch.alter_column("from_store_id", existing_type=sa.String(length=36), nullable=True)
        batch.alter_column("to_store_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("stock_transfers") as batch:
        batch.alter_column("from_store_id", existing_type=sa.String(length=36), nullable=False)
        batch.alter_column("to_store_id", existing_type=sa.String(length=36), nullable=False)
