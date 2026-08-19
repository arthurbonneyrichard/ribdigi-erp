"""Per-supplier early payment discount terms

Revision ID: 20260809_0061
Revises: 20260809_0060
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0061"
down_revision = "20260809_0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("parties") as batch:
        batch.add_column(sa.Column("early_pay_discount_pct", sa.Numeric(7, 4), nullable=True))
        batch.add_column(sa.Column("early_pay_discount_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("parties") as batch:
        batch.drop_column("early_pay_discount_days")
        batch.drop_column("early_pay_discount_pct")
