"""Add product variant dosage (BR-5.1).

Revision ID: 20260813_0087
Revises: 20260813_0086
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0087"
down_revision = "20260813_0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product_variants", sa.Column("dosage", sa.String(length=80), nullable=True))


def downgrade() -> None:
    op.drop_column("product_variants", "dosage")
