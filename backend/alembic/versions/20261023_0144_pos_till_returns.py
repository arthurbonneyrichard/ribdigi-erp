"""Till returns: a sales return can come from a till receipt instead of an invoice.

Revision ID: 20261023_0144
Revises: 20261022_0143
Create Date: 2026-10-23

Till (POS) sales have no sales invoice, so they could not be returned.
``sales_returns`` gains ``transaction_id`` (the till receipt), ``session_id``
(the shift that paid the refund) and ``store_id`` (for store filters when there
is no invoice). ``customer_id`` and ``sales_invoice_id`` become nullable, since a
walk-in till receipt has neither. Each step is skipped when already in place.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261023_0144"
down_revision = "20261022_0143"
branch_labels = None
depends_on = None


def _columns(bind) -> dict[str, dict]:
    return {c["name"]: c for c in sa.inspect(bind).get_columns("sales_returns")}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind)
    for name, target in (
        ("transaction_id", "transactions.id"),
        ("session_id", "pos_sessions.id"),
        ("store_id", "stores.id"),
    ):
        if name not in cols:
            op.add_column(
                "sales_returns",
                sa.Column(name, sa.String(length=36), sa.ForeignKey(target), nullable=True),
            )
            op.create_index(f"ix_sales_returns_{name}", "sales_returns", [name])
    cols = _columns(bind)
    for name in ("customer_id", "sales_invoice_id"):
        if name in cols and not cols[name]["nullable"]:
            op.alter_column("sales_returns", name, existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    cols = _columns(bind)
    for name in ("store_id", "session_id", "transaction_id"):
        if name in cols:
            op.drop_index(f"ix_sales_returns_{name}", table_name="sales_returns")
            op.drop_column("sales_returns", name)
