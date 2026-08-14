"""Add stock_movements.reason for coded adjustments (BR-5.2).

Revision ID: 20260814_0095
Revises: 20260813_0094
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0095"
down_revision = "20260813_0094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_movements",
        sa.Column("reason", sa.String(40), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stock_movements", "reason")
