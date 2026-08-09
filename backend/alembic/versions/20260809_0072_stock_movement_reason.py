"""Stock movement adjustment reason codes (Stage 2 I2 / BR-5.2)

Revision ID: 20260809_0072
Revises: 20260809_0071
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0072"
down_revision = "20260809_0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stock_movements") as batch:
        batch.add_column(sa.Column("reason", sa.String(length=40), nullable=True))
        batch.create_index("ix_stock_movements_reason", ["reason"])


def downgrade() -> None:
    with op.batch_alter_table("stock_movements") as batch:
        batch.drop_index("ix_stock_movements_reason")
        batch.drop_column("reason")
