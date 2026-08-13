"""Stage 167 E1 — pos_held_carts.expires_at for soft-reserve expiry.

Revision ID: 20260813_0095
Revises: 20260813_0094
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_0095"
down_revision = "20260813_0094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pos_held_carts",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pos_held_carts_expires_at", "pos_held_carts", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_pos_held_carts_expires_at", table_name="pos_held_carts")
    op.drop_column("pos_held_carts", "expires_at")
