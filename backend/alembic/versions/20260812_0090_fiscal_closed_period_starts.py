"""Add tenants.fiscal_closed_period_starts for Stage 118 F1 fiscal close console.

Revision ID: 20260812_0090
Revises: 20260811_0089
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0090"
down_revision = "20260811_0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("fiscal_closed_period_starts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "fiscal_closed_period_starts")
