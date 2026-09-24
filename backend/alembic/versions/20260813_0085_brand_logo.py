"""Add brand logo_url (BR-5.1).

Revision ID: 20260813_0085
Revises: 20260813_0084
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0085"
down_revision = "20260813_0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("brands", sa.Column("logo_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("brands", "logo_url")
