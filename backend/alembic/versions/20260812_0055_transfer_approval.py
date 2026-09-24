"""stock transfer dual-manager approval fields

Revision ID: 20260812_0055
Revises: 20260812_0054
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0055"
down_revision = "20260812_0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_transfers",
        sa.Column("approval_step", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "stock_transfers",
        sa.Column("approval_steps_required", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column("stock_transfers", sa.Column("source_approved_by", sa.String(length=36), nullable=True))
    op.add_column("stock_transfers", sa.Column("source_approved_at", sa.DateTime(), nullable=True))
    op.add_column("stock_transfers", sa.Column("dest_approved_by", sa.String(length=36), nullable=True))
    op.add_column("stock_transfers", sa.Column("dest_approved_at", sa.DateTime(), nullable=True))
    op.add_column("stock_transfers", sa.Column("rejected_by", sa.String(length=36), nullable=True))
    op.add_column("stock_transfers", sa.Column("rejection_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stock_transfers", "rejection_reason")
    op.drop_column("stock_transfers", "rejected_by")
    op.drop_column("stock_transfers", "dest_approved_at")
    op.drop_column("stock_transfers", "dest_approved_by")
    op.drop_column("stock_transfers", "source_approved_at")
    op.drop_column("stock_transfers", "source_approved_by")
    op.drop_column("stock_transfers", "approval_steps_required")
    op.drop_column("stock_transfers", "approval_step")
