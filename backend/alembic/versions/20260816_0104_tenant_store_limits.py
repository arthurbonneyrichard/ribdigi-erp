"""Tenant store entitlement columns (subscription max_stores + company allocation).

Revision ID: 20260816_0104
Revises: 20260815_0103
Create Date: 2026-08-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20260816_0104"
down_revision = "20260815_0103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("max_stores_override", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("store_limit", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "store_limit")
    op.drop_column("tenants", "max_stores_override")
