"""Bakery desk: recipes, baking, its own till, pre-orders, waste and payments.

Revision ID: 20261106_0155
Revises: 20261105_0154
Create Date: 2026-11-06

Everything a bakery does at the counter lands on its own tables, never on retail
``transactions`` or ``pos_sessions``. Skipped when the tables exist.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261106_0155"
down_revision = "20261105_0154"
branch_labels = None
depends_on = None

_ID = dict(type_=sa.String(length=36))


def _tenant():
    return sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def _money(name: str, nullable: bool = False):
    return sa.Column(name, sa.Numeric(14, 2), nullable=nullable, server_default=None if nullable else "0")


def _qty(name: str):
    return sa.Column(name, sa.Numeric(14, 3), nullable=False)


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("bakery_recipes"):
        return
    op.create_table(
        "bakery_recipes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        _qty("yield_qty"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "product_id", name="uq_bakery_recipe_product"),
    )
    op.create_table(
        "bakery_recipe_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("recipe_id", sa.String(length=36), sa.ForeignKey("bakery_recipes.id"), nullable=False, index=True),
        sa.Column("ingredient_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False, index=True),
        _qty("quantity"),
    )
    op.create_table(
        "bakery_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("batch_number", sa.String(length=40), nullable=False),
        sa.Column("recipe_id", sa.String(length=36), sa.ForeignKey("bakery_recipes.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False, index=True),
        _qty("batches"),
        _qty("made_qty"),
        _money("unit_cost"),
        _money("total_cost"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "batch_number", name="uq_bakery_batch_number"),
    )
    op.create_table(
        "bakery_waste",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False, index=True),
        _qty("quantity"),
        sa.Column("reason", sa.String(length=20), nullable=False),
        _money("unit_cost"),
        _money("total_cost"),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
    )
    op.create_table(
        "bakery_till_shifts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        _money("opening_cash"),
        _money("counted_cash", nullable=True),
        sa.Column("opened_by", sa.String(length=36), nullable=True),
        sa.Column("closed_by", sa.String(length=36), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "bakery_orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("order_number", sa.String(length=40), nullable=False),
        sa.Column("customer_name", sa.String(length=180), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=False, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        _money("subtotal"),
        _money("tax"),
        _money("total"),
        _money("deposit"),
        sa.Column("deposit_method", sa.String(length=20), nullable=True),
        sa.Column("deposit_journal_id", sa.String(length=36), nullable=True),
        sa.Column("deposit_outcome", sa.String(length=20), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.String(length=255), nullable=True),
        sa.Column("collected_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "order_number", name="uq_bakery_order_number"),
    )
    op.create_table(
        "bakery_order_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("bakery_orders.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        _qty("quantity"),
        _money("unit_price"),
        _money("tax"),
        _money("line_total"),
        sa.Column("note", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "bakery_sales",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("sale_number", sa.String(length=40), nullable=False),
        sa.Column("shift_id", sa.String(length=36), sa.ForeignKey("bakery_till_shifts.id"), nullable=True, index=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("bakery_orders.id"), nullable=True, index=True),
        sa.Column("customer_name", sa.String(length=180), nullable=True),
        sa.Column("payment_method", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        _money("subtotal"),
        _money("tax"),
        _money("total"),
        _money("cost_of_goods"),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("refund_reason", sa.String(length=255), nullable=True),
        sa.Column("refunded_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "sale_number", name="uq_bakery_sale_number"),
    )
    op.create_table(
        "bakery_sale_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("sale_id", sa.String(length=36), sa.ForeignKey("bakery_sales.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        _qty("quantity"),
        _money("unit_price"),
        _money("tax"),
        _money("line_total"),
    )
    op.create_table(
        "bakery_payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        _tenant(),
        sa.Column("shift_id", sa.String(length=36), sa.ForeignKey("bakery_till_shifts.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("method", sa.String(length=20), nullable=False),
        _money("amount"),
        sa.Column("sale_id", sa.String(length=36), sa.ForeignKey("bakery_sales.id"), nullable=True, index=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("bakery_orders.id"), nullable=True, index=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    for table in (
        "bakery_payments",
        "bakery_sale_lines",
        "bakery_sales",
        "bakery_order_lines",
        "bakery_orders",
        "bakery_till_shifts",
        "bakery_waste",
        "bakery_batches",
        "bakery_recipe_lines",
        "bakery_recipes",
    ):
        if _has_table(table):
            op.drop_table(table)
