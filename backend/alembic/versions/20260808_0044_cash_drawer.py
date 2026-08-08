"""POS cash drawer hardware settings on stores

Revision ID: 20260808_0044
Revises: 20260808_0043
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0044"
down_revision = "20260808_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stores",
        sa.Column("drawer_mode", sa.String(length=30), nullable=False, server_default="none"),
    )
    op.add_column("stores", sa.Column("drawer_host", sa.String(length=255), nullable=True))
    op.add_column(
        "stores",
        sa.Column("drawer_port", sa.Integer(), nullable=False, server_default="9100"),
    )
    op.add_column(
        "stores",
        sa.Column("drawer_open_on_cash", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("stores", "drawer_open_on_cash")
    op.drop_column("stores", "drawer_port")
    op.drop_column("stores", "drawer_host")
    op.drop_column("stores", "drawer_mode")
