"""compound tax components and reverse charge

Revision ID: 20260808_0030
Revises: 20260808_0029
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0030"
down_revision = "20260808_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tax_rates", sa.Column("components", sa.JSON(), nullable=True))
    op.add_column(
        "tax_rates",
        sa.Column("is_reverse_charge", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "sales_invoices",
        sa.Column("reverse_charge_tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("sales_invoices", "reverse_charge_tax")
    op.drop_column("tax_rates", "is_reverse_charge")
    op.drop_column("tax_rates", "components")
