"""FMCG selling: orders, payments, returns, and the cash a dispatch must hand in.

Revision ID: 20261106_0156
Revises: 20261106_0155
Create Date: 2026-11-06

A distributor sells on its own tables, not on retail sales documents.
Skipped when the tables exist.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261106_0156"
down_revision = "20261106_0155"
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.String(length=36), primary_key=True)


def _tenant():
    return sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def _money(name: str):
    return sa.Column(name, sa.Numeric(14, 2), nullable=False, server_default="0")


def _fk(name: str, target: str, nullable: bool = False):
    return sa.Column(name, sa.String(length=36), sa.ForeignKey(target), nullable=nullable, index=True)


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, name: str) -> bool:
    return any(c["name"] == name for c in sa.inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    for column in ("expected_cash", "counted_cash"):
        if not _has_column("fmcg_dispatches", column):
            op.add_column("fmcg_dispatches", sa.Column(column, sa.Numeric(14, 2), nullable=True))
    if _has_table("fmcg_orders"):
        return
    op.create_table(
        "fmcg_orders",
        _id(),
        _tenant(),
        sa.Column("order_number", sa.String(length=40), nullable=False),
        _fk("customer_id", "parties.id"),
        _fk("route_id", "fmcg_routes.id", True),
        _fk("dispatch_id", "fmcg_dispatches.id", True),
        sa.Column("rep_name", sa.String(length=150), nullable=True),
        sa.Column("terms", sa.String(length=20), nullable=False, server_default="credit"),
        sa.Column("status", sa.String(length=20), nullable=False, index=True),
        _money("subtotal"),
        _money("discount"),
        _money("tax"),
        _money("total"),
        _money("paid"),
        _money("returned"),
        _money("cost_of_goods"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("failed_reason", sa.String(length=255), nullable=True),
        sa.Column("cancel_reason", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "order_number", name="uq_fmcg_order_number"),
    )
    op.create_table(
        "fmcg_order_lines",
        _id(),
        _tenant(),
        _fk("order_id", "fmcg_orders.id"),
        _fk("product_id", "products.id"),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("returned_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        _money("unit_price"),
        _money("discount"),
        sa.Column("scheme_id", sa.String(length=36), nullable=True),
        _money("tax"),
        _money("line_total"),
    )
    op.create_table(
        "fmcg_payments",
        _id(),
        _tenant(),
        sa.Column("payment_number", sa.String(length=40), nullable=False),
        _fk("customer_id", "parties.id"),
        _fk("order_id", "fmcg_orders.id", True),
        _fk("dispatch_id", "fmcg_dispatches.id", True),
        sa.Column("method", sa.String(length=20), nullable=False),
        _money("amount"),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "payment_number", name="uq_fmcg_payment_number"),
    )
    op.create_table(
        "fmcg_returns",
        _id(),
        _tenant(),
        sa.Column("return_number", sa.String(length=40), nullable=False),
        _fk("order_id", "fmcg_orders.id"),
        _fk("customer_id", "parties.id"),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("resaleable", sa.Boolean(), nullable=False, server_default=sa.false()),
        _money("subtotal"),
        _money("tax"),
        _money("total"),
        _money("cost_of_goods"),
        sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "return_number", name="uq_fmcg_return_number"),
    )
    op.create_table(
        "fmcg_return_lines",
        _id(),
        _tenant(),
        _fk("return_id", "fmcg_returns.id"),
        _fk("order_line_id", "fmcg_order_lines.id"),
        _fk("product_id", "products.id"),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        _money("tax"),
        _money("line_total"),
    )


def downgrade() -> None:
    for table in ("fmcg_return_lines", "fmcg_returns", "fmcg_payments", "fmcg_order_lines", "fmcg_orders"):
        if _has_table(table):
            op.drop_table(table)
    for column in ("expected_cash", "counted_cash"):
        if _has_column("fmcg_dispatches", column):
            op.drop_column("fmcg_dispatches", column)
