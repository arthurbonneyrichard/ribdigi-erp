"""Add tenants.email_settings JSON for BR-20.3 SMTP overrides.

Revision ID: 20260814_0099
Revises: 20260814_0098
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0099"
down_revision = "20260814_0098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("email_settings", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "email_settings")
