"""expense attachment_url

Revision ID: 20260808_0027
Revises: 20260808_0026
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0027"
down_revision = "20260808_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("attachment_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("expenses", "attachment_url")
