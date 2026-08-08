"""purchase reverse charge self-assessment

Revision ID: 20260808_0035
Revises: 20260808_0034
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0035"
down_revision = "20260808_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_invoices",
        sa.Column("reverse_charge_tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "purchase_invoices",
        sa.Column("is_reverse_charge", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("purchase_invoices", "is_reverse_charge")
    op.drop_column("purchase_invoices", "reverse_charge_tax")
