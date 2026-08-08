"""tenant tax jurisdiction + TIN for government filing

Revision ID: 20260808_0041
Revises: 20260808_0040
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0041"
down_revision = "20260808_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("tax_jurisdiction", sa.String(length=10), nullable=False, server_default="GH"),
    )
    op.add_column(
        "tenants",
        sa.Column("tax_registration_number", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("tax_filing_period", sa.String(length=20), nullable=False, server_default="monthly"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "tax_filing_period")
    op.drop_column("tenants", "tax_registration_number")
    op.drop_column("tenants", "tax_jurisdiction")
