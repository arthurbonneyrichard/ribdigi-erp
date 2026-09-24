"""purchase order email delivery fields

Revision ID: 20260812_0050
Revises: 20260812_0049
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0050"
down_revision = "20260812_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("emailed_at", sa.DateTime(), nullable=True))
    op.add_column("purchase_orders", sa.Column("emailed_to", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("purchase_orders", "emailed_to")
    op.drop_column("purchase_orders", "emailed_at")
