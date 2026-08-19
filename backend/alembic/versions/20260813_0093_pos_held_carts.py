"""Stage 165 H1 — pos_held_carts (park only; no stock reservation).

Revision ID: 20260813_0093
Revises: 20260813_0092
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_0093"
down_revision = "20260813_0092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_held_carts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column(
            "session_id",
            sa.String(length=36),
            sa.ForeignKey("pos_sessions.id"),
            nullable=True,
        ),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("cart_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("held_at", sa.DateTime(), nullable=False),
        sa.Column("resumed_at", sa.DateTime(), nullable=True),
        sa.Column("discarded_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pos_held_carts_tenant_id", "pos_held_carts", ["tenant_id"])
    op.create_index("ix_pos_held_carts_user_id", "pos_held_carts", ["user_id"])
    op.create_index("ix_pos_held_carts_session_id", "pos_held_carts", ["session_id"])
    op.create_index("ix_pos_held_carts_status", "pos_held_carts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pos_held_carts_status", table_name="pos_held_carts")
    op.drop_index("ix_pos_held_carts_session_id", table_name="pos_held_carts")
    op.drop_index("ix_pos_held_carts_user_id", table_name="pos_held_carts")
    op.drop_index("ix_pos_held_carts_tenant_id", table_name="pos_held_carts")
    op.drop_table("pos_held_carts")
