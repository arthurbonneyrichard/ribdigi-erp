"""Add tenants.sms_settings JSON for tenant Twilio overrides.

Revision ID: 20260814_0100
Revises: 20260814_0099
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260814_0100"
down_revision = "20260814_0099"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("sms_settings", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "sms_settings")
