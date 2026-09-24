"""POS split tender payments table

Revision ID: 20260812_0047
Revises: 20260809_0046
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0047"
down_revision = "20260809_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "sale_id",
            sa.String(length=36),
            sa.ForeignKey("transactions.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("payment_method", sa.String(length=40), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column(
            "liquid_account_id",
            sa.String(length=36),
            sa.ForeignKey("accounts.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("pos_payments")
