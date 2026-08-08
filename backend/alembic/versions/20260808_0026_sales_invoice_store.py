"""sales invoice store_id

Revision ID: 20260808_0026
Revises: 20260808_0025
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0026"
down_revision = "20260808_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_invoices",
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
    )
    op.create_index("ix_sales_invoices_store_id", "sales_invoices", ["store_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_invoices_store_id", table_name="sales_invoices")
    op.drop_column("sales_invoices", "store_id")
