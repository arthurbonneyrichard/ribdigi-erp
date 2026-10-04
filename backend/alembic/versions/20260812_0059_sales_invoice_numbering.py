"""configurable sales invoice numbering prefix/series

Revision ID: 20260812_0059
Revises: 20260812_0058
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0059"
down_revision = "20260812_0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "sales_invoice_number_prefix",
            sa.String(length=20),
            nullable=False,
            server_default="INV",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "sales_invoice_number_next",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("sales_invoice_number_year", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "sales_invoice_number_year")
    op.drop_column("tenants", "sales_invoice_number_next")
    op.drop_column("tenants", "sales_invoice_number_prefix")
