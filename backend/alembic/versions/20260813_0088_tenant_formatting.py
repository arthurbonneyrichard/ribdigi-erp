"""Add tenant date/number/time formatting preferences (BR-20.2).

Revision ID: 20260813_0088
Revises: 20260813_0087
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0088"
down_revision = "20260813_0087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("date_format", sa.String(length=20), nullable=False, server_default="DD/MM/YYYY"),
    )
    op.add_column(
        "tenants",
        sa.Column("decimal_separator", sa.String(length=1), nullable=False, server_default="."),
    )
    op.add_column(
        "tenants",
        sa.Column("thousand_separator", sa.String(length=1), nullable=False, server_default=","),
    )
    op.add_column(
        "tenants",
        sa.Column("time_format", sa.String(length=5), nullable=False, server_default="24h"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "time_format")
    op.drop_column("tenants", "thousand_separator")
    op.drop_column("tenants", "decimal_separator")
    op.drop_column("tenants", "date_format")
