"""Bakery: deposits as a liability, input VAT, till over/short, discounts, split payment,
part refunds and stock counts.

Revision ID: 20261115_0185
Revises: 20261114_0182
Create Date: 2026-11-15
"""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "20261115_0185"
down_revision = "20261114_0182"
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _tenant() -> sa.Column:
    return sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True)


def upgrade() -> None:
    with op.batch_alter_table("bakery_orders") as batch:
        # Where the deposit was booked. NULL means the old 1100 booking.
        batch.add_column(sa.Column("deposit_account", sa.String(10), nullable=True))
    with op.batch_alter_table("bakery_stock_receipts") as batch:
        batch.add_column(sa.Column("tax", sa.Numeric(14, 2), nullable=False, server_default="0"))
    with op.batch_alter_table("bakery_expenses") as batch:
        batch.add_column(sa.Column("tax", sa.Numeric(14, 2), nullable=False, server_default="0"))
    with op.batch_alter_table("bakery_till_shifts") as batch:
        batch.add_column(sa.Column("variance_journal_id", sa.String(36), nullable=True))
    with op.batch_alter_table("bakery_sales") as batch:
        batch.add_column(sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("discount_reason", sa.String(255), nullable=True))
        batch.add_column(sa.Column("refunded_total", sa.Numeric(14, 2), nullable=False, server_default="0"))
    with op.batch_alter_table("bakery_sale_lines") as batch:
        batch.add_column(sa.Column("discount", sa.Numeric(14, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("refunded_qty", sa.Numeric(14, 3), nullable=False, server_default="0"))

    op.create_table(
        "bakery_refunds",
        _id(),
        _tenant(),
        sa.Column("refund_number", sa.String(40), nullable=False),
        sa.Column("sale_id", sa.String(36), sa.ForeignKey("bakery_sales.id"), nullable=False, index=True),
        sa.Column("shift_id", sa.String(36), sa.ForeignKey("bakery_till_shifts.id"), nullable=True),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cost_back", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("restock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, index=True),
        sa.UniqueConstraint("tenant_id", "refund_number", name="uq_bakery_refund_number"),
    )
    op.create_table(
        "bakery_refund_lines",
        _id(),
        _tenant(),
        sa.Column("refund_id", sa.String(36), sa.ForeignKey("bakery_refunds.id"), nullable=False, index=True),
        sa.Column("sale_line_id", sa.String(36), sa.ForeignKey("bakery_sale_lines.id"), nullable=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("tax", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "bakery_stock_counts",
        _id(),
        _tenant(),
        sa.Column("count_number", sa.String(40), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("value_change", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True, index=True),
        sa.UniqueConstraint("tenant_id", "count_number", name="uq_bakery_count_number"),
    )
    op.create_table(
        "bakery_stock_count_lines",
        _id(),
        _tenant(),
        sa.Column("count_id", sa.String(36), sa.ForeignKey("bakery_stock_counts.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("expected_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("counted_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("value_change", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )

    # Old full refunds become refund rows dated when they happened, so a refund counts in its own
    # period. Whether the food went back on the shelf is in the refund's audit record.
    bind = op.get_bind()
    sales = bind.execute(
        sa.text(
            "SELECT id, tenant_id, sale_number, payment_method, subtotal, tax, total, cost_of_goods, "
            "refund_reason, refunded_at, created_at FROM bakery_sales WHERE status = 'refunded'"
        )
    ).fetchall()
    for row in sales:
        restocked = False
        try:
            logs = bind.execute(
                sa.text(
                    "SELECT details FROM audit_logs WHERE tenant_id = :t AND action = 'bakery_refund' AND entity_id = :e"
                ),
                {"t": row.tenant_id, "e": row.id},
            ).fetchall()
            for (details,) in logs:
                data = details if isinstance(details, dict) else json.loads(details or "{}")
                restocked = restocked or bool(data.get("restocked"))
        except Exception:  # noqa: BLE001 - no audit table or unreadable details: assume not restocked
            restocked = False
        bind.execute(
            sa.text(
                "INSERT INTO bakery_refunds (id, tenant_id, refund_number, sale_id, method, subtotal, tax, total, "
                "cost_back, restock, reason, created_at) VALUES (:id, :t, :n, :s, :mth, :sub, :tax, :tot, :cb, :rs, :why, :at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "t": row.tenant_id,
                "n": f"RF-{row.sale_number}",
                "s": row.id,
                "mth": row.payment_method or "cash",
                "sub": row.subtotal or 0,
                "tax": row.tax or 0,
                "tot": row.total or 0,
                "cb": (row.cost_of_goods or 0) if restocked else 0,
                "rs": restocked,
                "why": row.refund_reason,
                "at": row.refunded_at or row.created_at,
            },
        )
        bind.execute(
            sa.text("UPDATE bakery_sales SET refunded_total = total WHERE id = :s"), {"s": row.id}
        )
        bind.execute(
            sa.text("UPDATE bakery_sale_lines SET refunded_qty = quantity WHERE sale_id = :s"), {"s": row.id}
        )


def downgrade() -> None:
    op.drop_table("bakery_stock_count_lines")
    op.drop_table("bakery_stock_counts")
    op.drop_table("bakery_refund_lines")
    op.drop_table("bakery_refunds")
    with op.batch_alter_table("bakery_sale_lines") as batch:
        batch.drop_column("refunded_qty")
        batch.drop_column("discount")
    with op.batch_alter_table("bakery_sales") as batch:
        batch.drop_column("refunded_total")
        batch.drop_column("discount_reason")
        batch.drop_column("discount")
    with op.batch_alter_table("bakery_till_shifts") as batch:
        batch.drop_column("variance_journal_id")
    with op.batch_alter_table("bakery_expenses") as batch:
        batch.drop_column("tax")
    with op.batch_alter_table("bakery_stock_receipts") as batch:
        batch.drop_column("tax")
    with op.batch_alter_table("bakery_orders") as batch:
        batch.drop_column("deposit_account")
