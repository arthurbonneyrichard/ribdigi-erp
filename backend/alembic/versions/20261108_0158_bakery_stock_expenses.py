"""Bakery: buying stock, expenses, what each sold item cost, and drivers who deliver and sell.

Revision ID: 20261108_0158
Revises: 20261106_0157
Create Date: 2026-11-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261108_0158"
down_revision = "20261106_0157"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, name: str) -> bool:
    return any(c["name"] == name for c in sa.inspect(op.get_bind()).get_columns(table))


def _money(name: str):
    return sa.Column(name, sa.Numeric(14, 2), nullable=False, server_default="0")


def upgrade() -> None:
    if not _has_column("bakery_till_shifts", "kind"):
        op.add_column("bakery_till_shifts", sa.Column("kind", sa.String(length=20), nullable=False, server_default="till"))
        op.create_index("ix_bakery_till_shifts_kind", "bakery_till_shifts", ["kind"])
    for name, column in (
        ("delivery", sa.Column("delivery", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("address", sa.Column("address", sa.Text(), nullable=True)),
        ("driver_id", sa.Column("driver_id", sa.String(length=36), nullable=True)),
        ("delivery_status", sa.Column("delivery_status", sa.String(length=20), nullable=True)),
        ("delivery_note", sa.Column("delivery_note", sa.String(length=255), nullable=True)),
        ("picked_up_at", sa.Column("picked_up_at", sa.DateTime(), nullable=True)),
    ):
        if not _has_column("bakery_orders", name):
            op.add_column("bakery_orders", column)
    if not any(i["name"] == "ix_bakery_orders_driver_id" for i in sa.inspect(op.get_bind()).get_indexes("bakery_orders")):
        op.create_index("ix_bakery_orders_driver_id", "bakery_orders", ["driver_id"])
    if not _has_column("bakery_sale_lines", "unit_cost"):
        op.add_column("bakery_sale_lines", sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True))
    if not _has_table("bakery_stock_receipts"):
        op.create_table(
            "bakery_stock_receipts",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("receipt_number", sa.String(length=40), nullable=False),
            sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False, index=True),
            sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
            _money("unit_cost"),
            _money("total"),
            sa.Column("paid_with", sa.String(length=20), nullable=False),
            sa.Column("supplier", sa.String(length=180), nullable=True),
            sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
            sa.UniqueConstraint("tenant_id", "receipt_number", name="uq_bakery_receipt_number"),
        )
    if not _has_table("bakery_expenses"):
        op.create_table(
            "bakery_expenses",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("expense_number", sa.String(length=40), nullable=False),
            sa.Column("category", sa.String(length=20), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=False),
            _money("amount"),
            sa.Column("paid_with", sa.String(length=20), nullable=False),
            sa.Column("spent_on", sa.Date(), nullable=False, index=True),
            sa.Column("shift_id", sa.String(length=36), sa.ForeignKey("bakery_till_shifts.id"), nullable=True, index=True),
            sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
            sa.UniqueConstraint("tenant_id", "expense_number", name="uq_bakery_expense_number"),
        )


def downgrade() -> None:
    for table in ("bakery_expenses", "bakery_stock_receipts"):
        if _has_table(table):
            op.drop_table(table)
    if _has_column("bakery_sale_lines", "unit_cost"):
        op.drop_column("bakery_sale_lines", "unit_cost")
    for name in ("picked_up_at", "delivery_note", "delivery_status", "driver_id", "address", "delivery"):
        if _has_column("bakery_orders", name):
            op.drop_column("bakery_orders", name)
    if _has_column("bakery_till_shifts", "kind"):
        op.drop_column("bakery_till_shifts", "kind")
