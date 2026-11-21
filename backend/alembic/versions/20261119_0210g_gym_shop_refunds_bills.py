"""Gym shop: refunded quantity on sale lines, supplier bills for stock bought on credit.

Revision ID: 20261119_0210g
Revises: 20261119_0209g
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0210g"
down_revision = "20261119_0209g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gym_shop_sale_lines", sa.Column("refunded_qty", sa.Integer(), nullable=False, server_default="0"))
    op.create_table(
        "gym_supplier_bills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("bill_number", sa.String(40), nullable=False), sa.Column("supplier_name", sa.String(150), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("gym_products.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("due_on", sa.Date(), index=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="open", index=True),
        sa.Column("paid_on", sa.Date()), sa.Column("pay_method", sa.String(20)),
        sa.Column("created_by", sa.String(36)), sa.Column("created_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("gym_supplier_bills")
    op.drop_column("gym_shop_sale_lines", "refunded_qty")
