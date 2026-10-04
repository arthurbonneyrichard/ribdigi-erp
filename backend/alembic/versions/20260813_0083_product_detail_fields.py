"""Add product description, weight, and dimensions (BR-5.1).

Revision ID: 20260813_0083
Revises: 20260813_0082
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0083"
down_revision = "20260813_0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("weight", sa.Numeric(14, 3), nullable=True))
    op.add_column("products", sa.Column("length", sa.Numeric(14, 3), nullable=True))
    op.add_column("products", sa.Column("width", sa.Numeric(14, 3), nullable=True))
    op.add_column("products", sa.Column("height", sa.Numeric(14, 3), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "height")
    op.drop_column("products", "width")
    op.drop_column("products", "length")
    op.drop_column("products", "weight")
    op.drop_column("products", "description")
