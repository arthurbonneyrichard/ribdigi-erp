"""Hotel shop till: its own sales and sale lines.

Revision ID: 20261031_0152
Revises: 20261030_0151
Create Date: 2026-10-31

A hotel shop sale (walk-up, or charged to a guest's room folio) lands here,
never in the retail transactions / pos_sessions tables. Skipped when the
tables exist.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261031_0152"
down_revision = "20261030_0151"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("hotel_shop_sales"):
        op.create_table(
            "hotel_shop_sales",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("sale_number", sa.String(length=40), nullable=False),
            sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
            sa.Column("shift_id", sa.String(length=36), sa.ForeignKey("hotel_cashier_shifts.id"), nullable=True),
            sa.Column("folio_id", sa.String(length=36), sa.ForeignKey("hotel_folios.id"), nullable=True),
            sa.Column("folio_charge_id", sa.String(length=36), sa.ForeignKey("hotel_folio_charges.id"), nullable=True),
            sa.Column("customer_name", sa.String(length=180), nullable=True),
            sa.Column("payment_method", sa.String(length=20), nullable=False),
            sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
            sa.Column("tax", sa.Numeric(14, 2), nullable=False),
            sa.Column("total", sa.Numeric(14, 2), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("refunded_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "sale_number", name="uq_hotel_shop_sale_number"),
        )
        for col in ("tenant_id", "sale_number", "store_id", "shift_id", "folio_id", "status", "created_at"):
            op.create_index(f"ix_hotel_shop_sales_{col}", "hotel_shop_sales", [col])
    if not _has_table("hotel_shop_sale_lines"):
        op.create_table(
            "hotel_shop_sale_lines",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("sale_id", sa.String(length=36), sa.ForeignKey("hotel_shop_sales.id"), nullable=False),
            sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
            sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
            sa.Column("tax", sa.Numeric(14, 2), nullable=False),
            sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        )
        for col in ("tenant_id", "sale_id", "product_id"):
            op.create_index(f"ix_hotel_shop_sale_lines_{col}", "hotel_shop_sale_lines", [col])


def downgrade() -> None:
    for name in ("hotel_shop_sale_lines", "hotel_shop_sales"):
        if _has_table(name):
            op.drop_table(name)
