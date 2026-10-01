"""Retail/wholesale trade channels, MOQ, price tiers, delivery notes.

Revision ID: 20261001_0132
Revises: 20261001_0131

Shared catalog/stock. Channel is retail|wholesale on quotes, orders, and
invoices. Does not invent gift cards, HIS, or a second POS.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20261001_0132"
down_revision = "20261001_0131"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "products" in tables:
        cols = {c["name"] for c in insp.get_columns("products")}
        if "min_order_qty" not in cols:
            op.add_column(
                "products",
                sa.Column("min_order_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
            )

    if "product_price_tiers" not in tables:
        op.create_table(
            "product_price_tiers",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.String(length=36),
                sa.ForeignKey("tenants.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "product_id",
                sa.String(length=36),
                sa.ForeignKey("products.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "customer_group_id",
                sa.String(length=36),
                sa.ForeignKey("customer_groups.id"),
                nullable=True,
                index=True,
            ),
            sa.Column("min_qty", sa.Numeric(14, 3), nullable=False, server_default="1"),
            sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    for table, default in (
        ("sales_quotations", "wholesale"),
        ("sales_orders", "wholesale"),
        ("sales_invoices", "retail"),
    ):
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "sales_channel" not in cols:
            op.add_column(
                table,
                sa.Column(
                    "sales_channel",
                    sa.String(length=20),
                    nullable=False,
                    server_default=default,
                ),
            )

    if "sales_orders" in tables:
        cols = {c["name"] for c in insp.get_columns("sales_orders")}
        if "delivery_note_number" not in cols:
            op.add_column(
                "sales_orders",
                sa.Column("delivery_note_number", sa.String(length=50), nullable=True),
            )
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_orders_tenant_delivery_note "
            "ON sales_orders (tenant_id, delivery_note_number) "
            "WHERE delivery_note_number IS NOT NULL"
        )

    if "sales_order_items" in tables:
        cols = {c["name"] for c in insp.get_columns("sales_order_items")}
        if "qty_fulfilled" not in cols:
            op.add_column(
                "sales_order_items",
                sa.Column("qty_fulfilled", sa.Numeric(14, 3), nullable=False, server_default="0"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "sales_order_items" in tables:
        cols = {c["name"] for c in insp.get_columns("sales_order_items")}
        if "qty_fulfilled" in cols:
            op.drop_column("sales_order_items", "qty_fulfilled")
    if "sales_orders" in tables:
        op.execute("DROP INDEX IF EXISTS uq_sales_orders_tenant_delivery_note")
        cols = {c["name"] for c in insp.get_columns("sales_orders")}
        if "delivery_note_number" in cols:
            op.drop_column("sales_orders", "delivery_note_number")
        if "sales_channel" in cols:
            op.drop_column("sales_orders", "sales_channel")
    for table in ("sales_quotations", "sales_invoices"):
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "sales_channel" in cols:
            op.drop_column(table, "sales_channel")
    if "product_price_tiers" in tables:
        op.drop_table("product_price_tiers")
    if "products" in tables:
        cols = {c["name"] for c in insp.get_columns("products")}
        if "min_order_qty" in cols:
            op.drop_column("products", "min_order_qty")
