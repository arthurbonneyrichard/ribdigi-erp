"""warehouse reorder policies and FEFO strict mode

Revision ID: 20260808_0034
Revises: 20260808_0033
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0034"
down_revision = "20260808_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warehouse_stocks",
        sa.Column("reorder_level", sa.Numeric(14, 3), nullable=False, server_default="0"),
    )
    op.add_column(
        "warehouse_stocks",
        sa.Column("reorder_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
    )
    op.add_column(
        "tenants",
        sa.Column("fefo_strict_warehouse", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("tenants", "fefo_strict_warehouse")
    op.drop_column("warehouse_stocks", "reorder_qty")
    op.drop_column("warehouse_stocks", "reorder_level")
