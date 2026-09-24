"""Tenant subscription packages + enabled modules.

Revision ID: 20260812_0070
Revises: 20260812_0069
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0070"
down_revision = "20260812_0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("package_code", sa.String(length=40), nullable=False, server_default="trial"),
    )
    op.add_column(
        "tenants",
        sa.Column("subscription_term_unit", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("subscription_term_value", sa.Integer(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("subscription_starts_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("subscription_ends_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("package_assigned_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("enabled_modules", sa.JSON(), nullable=True),
    )
    op.create_index("ix_tenants_package_code", "tenants", ["package_code"])


def downgrade() -> None:
    op.drop_index("ix_tenants_package_code", table_name="tenants")
    op.drop_column("tenants", "enabled_modules")
    op.drop_column("tenants", "package_assigned_at")
    op.drop_column("tenants", "subscription_ends_at")
    op.drop_column("tenants", "subscription_starts_at")
    op.drop_column("tenants", "subscription_term_value")
    op.drop_column("tenants", "subscription_term_unit")
    op.drop_column("tenants", "package_code")
