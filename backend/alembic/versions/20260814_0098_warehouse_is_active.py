"""Add warehouses.is_active for soft-deactivate (BR-2.4).

Revision ID: 20260814_0098
Revises: 20260814_0097
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0098"
down_revision = "20260814_0097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warehouses",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("warehouses", "is_active")
