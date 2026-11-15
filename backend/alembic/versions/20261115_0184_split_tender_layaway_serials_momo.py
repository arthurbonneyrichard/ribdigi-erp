"""Restaurant split payments, till held sales and layaways, serial numbers, Mobile Money prompts.

Revision ID: 20261115_0184
Revises: 20261115_0183
Create Date: 2026-11-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261115_0184"
down_revision = "20261115_0183"
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _tenant() -> sa.Column:
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False)


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("tracks_serials", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "restaurant_order_payments",
        _id(),
        _tenant(),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("restaurant_orders.id"), nullable=False),
        sa.Column("method", sa.String(32), nullable=False, server_default="cash"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_restaurant_order_payments_tenant_id", "restaurant_order_payments", ["tenant_id"])
    op.create_index("ix_restaurant_order_payments_order_id", "restaurant_order_payments", ["order_id"])

    op.create_table(
        "pos_held_sales",
        _id(),
        _tenant(),
        sa.Column("store_id", sa.String(36), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("cart", sa.JSON(), nullable=True),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pos_held_sales_tenant_id", "pos_held_sales", ["tenant_id"])
    op.create_index("ix_pos_held_sales_store_id", "pos_held_sales", ["store_id"])

    op.create_table(
        "pos_layaways",
        _id(),
        _tenant(),
        sa.Column("layaway_number", sa.String(40), nullable=False),
        sa.Column("store_id", sa.String(36), nullable=True),
        sa.Column("warehouse_id", sa.String(36), nullable=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("customer_name", sa.String(180), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("items", sa.JSON(), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "layaway_number", name="uq_pos_layaway_number"),
    )
    for col in ("tenant_id", "store_id", "customer_id", "status"):
        op.create_index(f"ix_pos_layaways_{col}", "pos_layaways", [col])

    op.create_table(
        "pos_layaway_payments",
        _id(),
        _tenant(),
        sa.Column("layaway_id", sa.String(36), sa.ForeignKey("pos_layaways.id"), nullable=False),
        sa.Column("method", sa.String(32), nullable=False, server_default="cash"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_pos_layaway_payments_tenant_id", "pos_layaway_payments", ["tenant_id"])
    op.create_index("ix_pos_layaway_payments_layaway_id", "pos_layaway_payments", ["layaway_id"])

    op.create_table(
        "product_serials",
        _id(),
        _tenant(),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("serial", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_stock"),
        sa.Column("warehouse_id", sa.String(36), nullable=True),
        sa.Column("received_ref", sa.String(80), nullable=True),
        sa.Column("sold_ref", sa.String(80), nullable=True),
        sa.Column("sold_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "product_id", "serial", name="uq_product_serial"),
    )
    for col in ("tenant_id", "product_id", "serial", "status"):
        op.create_index(f"ix_product_serials_{col}", "product_serials", [col])

    op.create_table(
        "till_payment_intents",
        _id(),
        _tenant(),
        sa.Column("reference", sa.String(64), nullable=False),
        sa.Column("desk", sa.String(20), nullable=False, server_default="retail"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GHS"),
        sa.Column("phone_hint", sa.String(20), nullable=True),
        sa.Column("provider", sa.String(10), nullable=False, server_default="mtn"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("message", sa.String(255), nullable=True),
        sa.Column("used_ref", sa.String(80), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("reference", name="uq_till_payment_reference"),
    )
    op.create_index("ix_till_payment_intents_tenant_id", "till_payment_intents", ["tenant_id"])
    op.create_index("ix_till_payment_intents_status", "till_payment_intents", ["status"])


def downgrade() -> None:
    for table in (
        "till_payment_intents",
        "product_serials",
        "pos_layaway_payments",
        "pos_layaways",
        "pos_held_sales",
        "restaurant_order_payments",
    ):
        op.drop_table(table)
    with op.batch_alter_table("products") as batch:
        batch.drop_column("tracks_serials")
