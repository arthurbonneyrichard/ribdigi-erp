"""Gym shop: products, sales and sale lines.

Revision ID: 20261119_0209g
Revises: 20261119_0208g
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0209g"
down_revision = "20261119_0208g"
branch_labels = None
depends_on = None


def _fk(name, table, nullable=False):
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=nullable, index=True)


def upgrade() -> None:
    op.create_table(
        "gym_products", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"),
        sa.Column("name", sa.String(150), nullable=False), sa.Column("sku", sa.String(60)),
        sa.Column("price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("stock_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_gym_product_name"),
    )
    op.create_table(
        "gym_shop_sales", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"),
        sa.Column("sale_number", sa.String(40), nullable=False), _fk("member_id", "gym_members", True),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"), sa.Column("tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default="0"), sa.Column("cost_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", sa.String(36)), sa.Column("created_by", sa.String(36)),
        sa.Column("created_at", sa.DateTime(), index=True),
    )
    op.create_table(
        "gym_shop_sale_lines", sa.Column("id", sa.String(36), primary_key=True), _fk("tenant_id", "tenants"),
        _fk("sale_id", "gym_shop_sales"), _fk("product_id", "gym_products"),
        sa.Column("name", sa.String(150), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False), sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
    )


def downgrade() -> None:
    for t in ("gym_shop_sale_lines", "gym_shop_sales", "gym_products"):
        op.drop_table(t)
