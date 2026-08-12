"""print branding header/footer and template defaults

Revision ID: 20260812_0061
Revises: 20260812_0060
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0061"
down_revision = "20260812_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("print_branding", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "print_branding")
