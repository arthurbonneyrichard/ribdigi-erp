"""tenant logo_url media

Revision ID: 20260808_0022
Revises: 20260808_0021
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0022"
down_revision = "20260808_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("logo_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "logo_url")
