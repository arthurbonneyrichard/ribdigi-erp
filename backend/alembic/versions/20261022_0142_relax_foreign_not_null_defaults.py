"""Relax hybrid extra NOT NULL columns from another tree's migrate.

Revision ID: 20261022_0142
Revises: 20261021_0141
Create Date: 2026-10-22

A disposable Docker DB was migrated by a different checkout that added
NOT NULL columns this tree's models/INSERTs do not fill. This revision
does not copy that history.

If a listed column exists: set a server default or drop NOT NULL so
inserts succeed. If it does not exist: skip, except
sales_invoices.credit_limit_overridden which this tree now maps.

Do not apply to live ribdigi_erp from this work.
"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = "20261022_0142"
down_revision = "20261021_0141"
branch_labels = None
depends_on = None

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")

# Extra columns another tree added as NOT NULL with no default.
# Do not ADD these — this tree's models do not own them.
_SET_DEFAULTS: tuple[tuple[str, str, str], ...] = (
    ("parties", "created_at", "now()"),
    ("parties", "updated_at", "now()"),
    ("stock_reservations", "updated_at", "now()"),
    ("sales_invoices", "credit_limit_overridden", "false"),
    ("recurring_expenses", "skip_next", "false"),
    ("purchase_order_amendments", "revision", "1"),
)

_DROP_NOT_NULL: tuple[tuple[str, str], ...] = (
    ("custom_roles", "slug"),
    ("ai_queries", "message"),
    ("ai_queries", "answer"),
)


def _quote(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"unsafe identifier {name!r}")
    return name


def _dialect_name(bind) -> str:
    return (getattr(getattr(bind, "dialect", None), "name", None) or "").lower()


def _table_columns(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _default_sql(bind, postgres_default: str) -> str:
    dialect = _dialect_name(bind)
    if postgres_default == "now()":
        return "now()" if dialect == "postgresql" else "CURRENT_TIMESTAMP"
    if postgres_default == "false":
        return "false" if dialect == "postgresql" else "0"
    return postgres_default


def _set_default_if_exists(bind, table: str, column: str, postgres_default: str) -> str:
    if column not in _table_columns(bind, table):
        return "skipped"
    if _dialect_name(bind) != "postgresql":
        # SQLite has no ALTER COLUMN SET DEFAULT; local/CI fixtures use create_all.
        return "skipped"
    default_sql = _default_sql(bind, postgres_default)
    bind.execute(
        sa.text(
            f"ALTER TABLE {_quote(table)} ALTER COLUMN {_quote(column)} "
            f"SET DEFAULT {default_sql}"
        )
    )
    return "set_default"


def _drop_not_null_if_exists(bind, table: str, column: str) -> str:
    if column not in _table_columns(bind, table):
        return "skipped"
    dialect = _dialect_name(bind)
    if dialect == "postgresql":
        bind.execute(
            sa.text(
                f"ALTER TABLE {_quote(table)} ALTER COLUMN {_quote(column)} DROP NOT NULL"
            )
        )
        return "drop_not_null"
    try:
        bind.execute(
            sa.text(
                f"ALTER TABLE {_quote(table)} ALTER COLUMN {_quote(column)} DROP NOT NULL"
            )
        )
        return "drop_not_null"
    except Exception:
        # Older SQLite cannot DROP NOT NULL in place; skip rather than rebuild.
        return "skipped"


def _ensure_credit_limit_overridden(bind) -> str:
    table = "sales_invoices"
    column = "credit_limit_overridden"
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return "skipped"
    if column in _table_columns(bind, table):
        return _set_default_if_exists(bind, table, column, "false")
    dialect = _dialect_name(bind)
    if dialect == "postgresql":
        bind.execute(
            sa.text(
                f"ALTER TABLE {_quote(table)} "
                f"ADD COLUMN IF NOT EXISTS {_quote(column)} "
                "BOOLEAN NOT NULL DEFAULT false"
            )
        )
        return "added"
    bind.execute(
        sa.text(
            f"ALTER TABLE {_quote(table)} ADD COLUMN {_quote(column)} "
            "BOOLEAN NOT NULL DEFAULT 0"
        )
    )
    return "added"


def apply_relaxations(bind) -> list[tuple[str, str, str]]:
    """Apply hybrid-column relaxations. Safe to call twice. Returns applied actions."""
    applied: list[tuple[str, str, str]] = []
    for table, column, default_sql in _SET_DEFAULTS:
        if table == "sales_invoices" and column == "credit_limit_overridden":
            continue
        action = _set_default_if_exists(bind, table, column, default_sql)
        applied.append((table, column, action))
    for table, column in _DROP_NOT_NULL:
        applied.append((table, column, _drop_not_null_if_exists(bind, table, column)))
    applied.append(
        ("sales_invoices", "credit_limit_overridden", _ensure_credit_limit_overridden(bind))
    )
    return applied


def upgrade() -> None:
    apply_relaxations(op.get_bind())


def downgrade() -> None:
    # Do not re-impose NOT NULL or drop defaults that keep hybrid inserts working.
    return
