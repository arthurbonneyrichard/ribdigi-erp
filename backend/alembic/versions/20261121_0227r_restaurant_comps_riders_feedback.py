"""Restaurant: bill discounts and comps, guest on the bill, rider tracking, guest feedback.

Revision ID: 20261121_0227r
Revises: 20261121_0226h
Create Date: 2026-11-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261121_0227r"
down_revision = "20261121_0226h"
branch_labels = None
depends_on = None

_COLS = [
    sa.Column("party_id", sa.String(36), nullable=True),
    sa.Column("discount_kind", sa.String(10), nullable=True),
    sa.Column("discount_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
    sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
    sa.Column("discount_reason", sa.String(200), nullable=True),
    sa.Column("discount_by", sa.String(36), nullable=True),
    sa.Column("rider_name", sa.String(120), nullable=True),
    sa.Column("rider_phone", sa.String(50), nullable=True),
    sa.Column("delivery_status", sa.String(20), nullable=True),
    sa.Column("dispatched_at", sa.DateTime(), nullable=True),
    sa.Column("delivered_at", sa.DateTime(), nullable=True),
]


def upgrade() -> None:
    for col in _COLS:
        op.add_column("restaurant_orders", col)
    op.create_index("ix_restaurant_orders_party_id", "restaurant_orders", ["party_id"])
    op.create_table(
        "restaurant_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("order_id", sa.String(36), nullable=True, index=True),
        sa.Column("order_number", sa.String(40), nullable=True),
        sa.Column("guest_name", sa.String(180), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source", sa.String(12), nullable=False, server_default="staff"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("restaurant_feedback")
    op.drop_index("ix_restaurant_orders_party_id", table_name="restaurant_orders")
    for col in reversed(_COLS):
        op.drop_column("restaurant_orders", col.name)
