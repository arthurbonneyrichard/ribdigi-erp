"""Hybrid extra NOT NULL columns: migration is skip-safe and idempotent."""

from __future__ import annotations

from importlib.machinery import SourceFileLoader
from pathlib import Path

from sqlalchemy import create_engine, text

from app import models as m

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic" / "versions" / "20261022_0142_relax_foreign_not_null_defaults.py"


def _load_migration():
    return SourceFileLoader("alembic_20261022_0142", str(MIGRATION)).load_module()


def test_sales_invoice_model_persists_credit_limit_overridden():
    col = m.SalesInvoice.__table__.c.credit_limit_overridden
    assert col.nullable is False
    assert str(col.server_default.arg) in {"false", "0"}


def test_migration_skips_missing_columns_and_is_idempotent():
    mig = _load_migration()
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE parties (id VARCHAR PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("CREATE TABLE stock_reservations (id VARCHAR PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE recurring_expenses (id VARCHAR PRIMARY KEY)"))
        conn.execute(
            text("CREATE TABLE purchase_order_amendments (id VARCHAR PRIMARY KEY)")
        )
        conn.execute(text("CREATE TABLE custom_roles (id VARCHAR PRIMARY KEY)"))
        conn.execute(text("CREATE TABLE ai_queries (id VARCHAR PRIMARY KEY)"))
        first = mig.apply_relaxations(conn)
        second = mig.apply_relaxations(conn)
    by_col = {(table, column): action for table, column, action in first}
    assert by_col[("parties", "created_at")] == "skipped"
    assert by_col[("parties", "updated_at")] == "skipped"
    assert by_col[("stock_reservations", "updated_at")] == "skipped"
    assert by_col[("recurring_expenses", "skip_next")] == "skipped"
    assert by_col[("purchase_order_amendments", "revision")] == "skipped"
    assert by_col[("custom_roles", "slug")] == "skipped"
    assert by_col[("ai_queries", "message")] == "skipped"
    assert by_col[("ai_queries", "answer")] == "skipped"
    assert by_col[("sales_invoices", "credit_limit_overridden")] == "skipped"
    assert first == second


def test_migration_existing_extra_columns_are_safe_twice_on_sqlite():
    """SQLite cannot ALTER COLUMN SET DEFAULT; helpers must no-op, not error."""
    mig = _load_migration()
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE parties ("
                "id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, "
                "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE stock_reservations ("
                "id VARCHAR PRIMARY KEY, updated_at DATETIME NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE sales_invoices ("
                "id VARCHAR PRIMARY KEY, credit_limit_overridden BOOLEAN NOT NULL "
                "DEFAULT 0)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE recurring_expenses ("
                "id VARCHAR PRIMARY KEY, skip_next BOOLEAN NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE purchase_order_amendments ("
                "id VARCHAR PRIMARY KEY, revision INTEGER NOT NULL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE custom_roles ("
                "id VARCHAR PRIMARY KEY, slug VARCHAR NOT NULL DEFAULT '')"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE ai_queries ("
                "id VARCHAR PRIMARY KEY, message TEXT NOT NULL DEFAULT '', "
                "answer TEXT NOT NULL DEFAULT '')"
            )
        )
        first = mig.apply_relaxations(conn)
        second = mig.apply_relaxations(conn)

    by_col = {(table, column): action for table, column, action in first}
    assert by_col[("parties", "created_at")] == "skipped"
    assert by_col[("stock_reservations", "updated_at")] == "skipped"
    assert by_col[("sales_invoices", "credit_limit_overridden")] == "skipped"
    assert by_col[("recurring_expenses", "skip_next")] == "skipped"
    assert by_col[("purchase_order_amendments", "revision")] == "skipped"
    assert by_col[("custom_roles", "slug")] in {"drop_not_null", "skipped"}
    assert by_col[("ai_queries", "message")] in {"drop_not_null", "skipped"}
    assert first == second
    assert mig._SET_DEFAULTS[0] == ("parties", "created_at", "now()")
    assert ("custom_roles", "slug") in mig._DROP_NOT_NULL


def test_migration_adds_credit_limit_overridden_when_model_needs_it():
    mig = _load_migration()
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE sales_invoices (id VARCHAR PRIMARY KEY)"))
        first = mig.apply_relaxations(conn)
        second = mig.apply_relaxations(conn)
        conn.execute(text("INSERT INTO sales_invoices (id) VALUES ('s1')"))
        value = conn.execute(
            text("SELECT credit_limit_overridden FROM sales_invoices")
        ).scalar_one()
    by_col = {(table, column): action for table, column, action in first}
    assert by_col[("sales_invoices", "credit_limit_overridden")] == "added"
    assert second[-1][0:2] == ("sales_invoices", "credit_limit_overridden")
    assert second[-1][2] in {"set_default", "skipped"}
    assert value in {0, False}
