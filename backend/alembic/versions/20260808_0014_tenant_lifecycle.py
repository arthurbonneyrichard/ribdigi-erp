"""tenant profile and lifecycle fields

Revision ID: 20260808_0014
Revises: 20260808_0013
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0014"
down_revision = "20260808_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("phone", sa.String(length=40), nullable=True))
    op.add_column("tenants", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("tenants", sa.Column("website", sa.String(length=255), nullable=True))
    op.add_column("tenants", sa.Column("address", sa.Text(), nullable=True))
    op.add_column(
        "tenants",
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Africa/Accra"),
    )
    op.add_column(
        "tenants",
        sa.Column("fiscal_year_start", sa.String(length=5), nullable=False, server_default="01-01"),
    )
    op.add_column("tenants", sa.Column("suspended_at", sa.DateTime(), nullable=True))
    op.add_column("tenants", sa.Column("suspended_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "suspended_reason")
    op.drop_column("tenants", "suspended_at")
    op.drop_column("tenants", "fiscal_year_start")
    op.drop_column("tenants", "timezone")
    op.drop_column("tenants", "address")
    op.drop_column("tenants", "website")
    op.drop_column("tenants", "email")
    op.drop_column("tenants", "phone")
