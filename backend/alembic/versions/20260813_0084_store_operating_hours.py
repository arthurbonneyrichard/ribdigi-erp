"""Add store operating_hours JSON (BR-2.3).

Revision ID: 20260813_0084
Revises: 20260813_0083
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0084"
down_revision = "20260813_0083"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stores",
        sa.Column("operating_hours", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stores", "operating_hours")
