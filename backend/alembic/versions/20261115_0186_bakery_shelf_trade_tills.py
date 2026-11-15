"""Bakery: shelf life and day-old prices, allergens and labels, purchase units, shelf levels,
trade customers (standing orders, invoices on credit, payments), suppliers, and more than one till.

Revision ID: 20261115_0186
Revises: 20261115_0185
Create Date: 2026-11-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261115_0186"
down_revision = "20261115_0185"
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _tenant() -> sa.Column:
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def _money(name: str) -> sa.Column:
    return sa.Column(name, sa.Numeric(14, 2), nullable=False, server_default="0")


def upgrade() -> None:
    op.create_table(
        "bakery_item_settings",
        _id(),
        _tenant(),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("shelf_life_days", sa.Integer(), nullable=True),
        sa.Column("day_old_discount_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("allergens", sa.JSON(), nullable=True),
        sa.Column("ingredients_text", sa.Text(), nullable=True),
        sa.Column("net_weight", sa.String(40), nullable=True),
        sa.Column("storage_note", sa.String(200), nullable=True),
        sa.Column("stock_unit", sa.String(20), nullable=True),
        sa.Column("purchase_unit", sa.String(30), nullable=True),
        sa.Column("units_per_purchase", sa.Numeric(14, 3), nullable=True),
        sa.Column("par_level", sa.Numeric(14, 3), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "product_id", name="uq_bakery_item_settings_product"),
    )
    with op.batch_alter_table("bakery_batches") as batch:
        batch.add_column(sa.Column("best_before", sa.Date(), nullable=True))
    with op.batch_alter_table("bakery_till_shifts") as batch:
        batch.add_column(sa.Column("till_name", sa.String(60), nullable=True))

    op.create_table(
        "bakery_suppliers",
        _id(),
        _tenant(),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("terms_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_bakery_supplier_name"),
    )
    with op.batch_alter_table("bakery_stock_receipts") as batch:
        batch.add_column(sa.Column("supplier_id", sa.String(36), sa.ForeignKey("bakery_suppliers.id"), nullable=True))
        batch.add_column(sa.Column("bill_number", sa.String(60), nullable=True))
    op.create_table(
        "bakery_supplier_payments",
        _id(),
        _tenant(),
        sa.Column("payment_number", sa.String(40), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("bakery_suppliers.id"), nullable=False, index=True),
        sa.Column("shift_id", sa.String(36), sa.ForeignKey("bakery_till_shifts.id"), nullable=True),
        sa.Column("method", sa.String(20), nullable=False),
        _money("amount"),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, index=True),
        sa.UniqueConstraint("tenant_id", "payment_number", name="uq_bakery_supplier_payment_number"),
    )

    op.create_table(
        "bakery_customers",
        _id(),
        _tenant(),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        _money("credit_limit"),
        sa.Column("trade_discount_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("terms_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "name", name="uq_bakery_customer_name"),
    )
    op.create_table(
        "bakery_standing_orders",
        _id(),
        _tenant(),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("bakery_customers.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        # Seven characters, Monday first: "1111100" is weekdays.
        sa.Column("days", sa.String(7), nullable=False, server_default="1111111"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "bakery_invoices",
        _id(),
        _tenant(),
        sa.Column("invoice_number", sa.String(40), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("bakery_customers.id"), nullable=False, index=True),
        sa.Column("invoice_date", sa.Date(), nullable=False, index=True),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("from_standing", sa.Boolean(), nullable=False, server_default=sa.false()),
        _money("subtotal"),
        _money("tax"),
        _money("total"),
        _money("paid"),
        _money("cost_of_goods"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("void_reason", sa.String(255), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("void_restocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, index=True),
        sa.UniqueConstraint("tenant_id", "invoice_number", name="uq_bakery_invoice_number"),
    )
    op.create_table(
        "bakery_invoice_lines",
        _id(),
        _tenant(),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("bakery_invoices.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        _money("unit_price"),
        _money("tax"),
        _money("line_total"),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True),
    )
    op.create_table(
        "bakery_customer_payments",
        _id(),
        _tenant(),
        sa.Column("payment_number", sa.String(40), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("bakery_customers.id"), nullable=False, index=True),
        sa.Column("shift_id", sa.String(36), sa.ForeignKey("bakery_till_shifts.id"), nullable=True),
        sa.Column("method", sa.String(20), nullable=False),
        _money("amount"),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, index=True),
        sa.UniqueConstraint("tenant_id", "payment_number", name="uq_bakery_customer_payment_number"),
    )


def downgrade() -> None:
    op.drop_table("bakery_customer_payments")
    op.drop_table("bakery_invoice_lines")
    op.drop_table("bakery_invoices")
    op.drop_table("bakery_standing_orders")
    op.drop_table("bakery_customers")
    op.drop_table("bakery_supplier_payments")
    with op.batch_alter_table("bakery_stock_receipts") as batch:
        batch.drop_column("bill_number")
        batch.drop_column("supplier_id")
    op.drop_table("bakery_suppliers")
    with op.batch_alter_table("bakery_till_shifts") as batch:
        batch.drop_column("till_name")
    with op.batch_alter_table("bakery_batches") as batch:
        batch.drop_column("best_before")
    op.drop_table("bakery_item_settings")
