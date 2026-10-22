"""Create tables a hybrid-migrated database skipped; relax purchase_requests.supplier_id.

Revision ID: 20261022_0143
Revises: 20261022_0142
Create Date: 2026-10-22

A read-only check of the live database on 22 Oct 2026 (alembic_version
20261022_0142) found:

- ``cash_transfers`` missing (0072 never ran there): Accounting cash/bank
  transfers fail.
- ``ai_security_alerts`` missing (0068 never ran there): the AI security
  monitor and its Celery scan fail.
- ``purchase_requests.supplier_id`` NOT NULL with no default, added by another
  tree; this tree's models use ``preferred_supplier_id``, so creating a
  purchase request fails.

It also adds ``tenant_billing_accounts.price_override_amount`` and
``price_override_currency``, which the models map but no earlier revision
created (live already has them; a fresh database did not).

Each step is skipped when already in place, so databases that ran 0068/0072
normally are untouched. Nothing is dropped.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261022_0143"
down_revision = "20261022_0142"
branch_labels = None
depends_on = None


def _has_table(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table)


def _columns(bind, table: str) -> dict[str, dict]:
    if not _has_table(bind, table):
        return {}
    return {c["name"]: c for c in sa.inspect(bind).get_columns(table)}


def _ensure_cash_transfers(bind) -> str:
    if _has_table(bind, "cash_transfers"):
        return "exists"
    op.create_table(
        "cash_transfers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="transfer"),
        sa.Column("from_account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("to_account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("journal_entry_id", sa.String(length=36), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_cash_transfers_tenant_id", "cash_transfers", ["tenant_id"])
    op.create_index("ix_cash_transfers_from_account_id", "cash_transfers", ["from_account_id"])
    op.create_index("ix_cash_transfers_to_account_id", "cash_transfers", ["to_account_id"])
    return "created"


def _ensure_ai_security_alerts(bind) -> str:
    if _has_table(bind, "ai_security_alerts"):
        return "exists"
    op.create_table(
        "ai_security_alerts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "fingerprint", name="uq_ai_security_alerts_tenant_fingerprint"),
    )
    for col in ("tenant_id", "kind", "risk_score", "user_id", "status", "created_at"):
        op.create_index(f"ix_ai_security_alerts_{col}", "ai_security_alerts", [col])
    return "created"


def _relax_purchase_request_supplier_id(bind) -> str:
    col = _columns(bind, "purchase_requests").get("supplier_id")
    if not col or col.get("nullable", True):
        return "skipped"
    if bind.dialect.name != "postgresql":
        # SQLite cannot DROP NOT NULL in place; local/CI fixtures use create_all.
        return "skipped"
    bind.execute(sa.text("ALTER TABLE purchase_requests ALTER COLUMN supplier_id DROP NOT NULL"))
    return "drop_not_null"


def _ensure_billing_price_override(bind) -> list[tuple[str, str]]:
    # Models map these but no earlier revision adds them; the live database already
    # has them, a fresh database did not.
    cols = _columns(bind, "tenant_billing_accounts")
    if not cols:
        return [("tenant_billing_accounts.price_override_*", "skipped")]
    out = []
    for name, type_ in (("price_override_amount", sa.Numeric(14, 2)), ("price_override_currency", sa.String(length=3))):
        if name in cols:
            out.append((f"tenant_billing_accounts.{name}", "exists"))
        else:
            op.add_column("tenant_billing_accounts", sa.Column(name, type_, nullable=True))
            out.append((f"tenant_billing_accounts.{name}", "added"))
    return out


def apply(bind) -> list[tuple[str, str]]:
    """Safe to call twice. Returns (object, action) pairs."""
    return [
        ("cash_transfers", _ensure_cash_transfers(bind)),
        ("ai_security_alerts", _ensure_ai_security_alerts(bind)),
        ("purchase_requests.supplier_id", _relax_purchase_request_supplier_id(bind)),
        *_ensure_billing_price_override(bind),
    ]


def upgrade() -> None:
    apply(op.get_bind())


def downgrade() -> None:
    # Keep the tables and the relaxed column: dropping them would lose live data.
    return
