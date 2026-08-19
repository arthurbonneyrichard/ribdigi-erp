"""Stage 166 S1 — pos_held_carts soft stock reservation columns.

Revision ID: 20260813_0094
Revises: 20260813_0093
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_0094"
down_revision = "20260813_0093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pos_held_carts",
        sa.Column("stock_reserved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "pos_held_carts",
        sa.Column("reservation_lines", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pos_held_carts", "reservation_lines")
    op.drop_column("pos_held_carts", "stock_reserved")
