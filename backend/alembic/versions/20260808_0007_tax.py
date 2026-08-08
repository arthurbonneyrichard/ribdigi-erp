"""tax rate enrichment

Revision ID: 20260808_0007
Revises: 20260808_0006
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0007"
down_revision = "20260808_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tax_rates", sa.Column("tax_type", sa.String(length=30), nullable=False, server_default="vat"))
    op.add_column(
        "tax_rates",
        sa.Column("pricing_mode", sa.String(length=20), nullable=False, server_default="exclusive"),
    )
    op.add_column("tax_rates", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.add_column(
        "products",
        sa.Column("tax_rate_id", sa.String(length=36), sa.ForeignKey("tax_rates.id"), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("tax_exempt", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("products", "tax_exempt")
    op.drop_column("products", "tax_rate_id")
    op.drop_column("tax_rates", "is_active")
    op.drop_column("tax_rates", "pricing_mode")
    op.drop_column("tax_rates", "tax_type")
