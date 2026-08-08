"""credit aging due dates and supplier payments

Revision ID: 20260808_0009
Revises: 20260808_0008
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0009"
down_revision = "20260808_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_invoices", sa.Column("due_date", sa.DateTime(), nullable=True))
    op.add_column(
        "purchase_orders",
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column("purchase_orders", sa.Column("due_date", sa.DateTime(), nullable=True))

    op.create_table(
        "supplier_payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("payment_number", sa.String(length=50), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("purchase_order_id", sa.String(length=36), sa.ForeignKey("purchase_orders.id"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=40), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "payment_number"),
    )
    op.create_index("ix_supplier_payments_supplier", "supplier_payments", ["supplier_id"])


def downgrade() -> None:
    op.drop_table("supplier_payments")
    op.drop_column("purchase_orders", "due_date")
    op.drop_column("purchase_orders", "paid_amount")
    op.drop_column("sales_invoices", "due_date")
