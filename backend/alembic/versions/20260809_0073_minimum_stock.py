"""Product and warehouse minimum_stock (Stage 2 I3 / BR-5.5)

Revision ID: 20260809_0073
Revises: 20260809_0072
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0073"
down_revision = "20260809_0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column("minimum_stock", sa.Numeric(14, 3), nullable=False, server_default="0")
        )
    with op.batch_alter_table("warehouse_stocks") as batch:
        batch.add_column(
            sa.Column("minimum_stock", sa.Numeric(14, 3), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("warehouse_stocks") as batch:
        batch.drop_column("minimum_stock")
    with op.batch_alter_table("products") as batch:
        batch.drop_column("minimum_stock")
