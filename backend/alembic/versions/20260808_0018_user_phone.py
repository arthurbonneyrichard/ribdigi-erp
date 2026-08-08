"""user phone for SMS

Revision ID: 20260808_0018
Revises: 20260808_0017
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0018"
down_revision = "20260808_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "phone")
