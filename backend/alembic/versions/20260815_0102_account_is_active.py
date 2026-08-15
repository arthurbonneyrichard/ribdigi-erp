"""Add accounts.is_active for COA soft-deactivate (BR-10.1).

Revision ID: 20260815_0102
Revises: 20260815_0101
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa


revision = "20260815_0102"
down_revision = "20260815_0101"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("accounts", "is_active")
