"""Idempotent, non-destructive schema alignment for hybrid production DBs.

Live Postgres may follow `main` (company_id, plan_code, conversion_factor, …)
while production ORM expects other columns (package_code, conversion_ratio, …).
This adds missing ORM columns and sets defaults on extra NOT NULL live columns
so SELECT/INSERT via the ORM succeeds. Never DROP/TRUNCATE.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy import Boolean, Date, DateTime, Integer, JSON, Numeric, String, Text, inspect, text
from sqlalchemy.engine import Connection

from app.models import Base

logger = logging.getLogger("ribdigi.schema_align")

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")

_ALIAS_COPIES = (
    ("tenants", "package_code", "plan_code"),
    ("tenants", "contact_person", "contact_person_name"),
    ("tenants", "purchase_approval_matrix", "purchase_request_approval_matrix"),
    ("units_of_measure", "conversion_ratio", "conversion_factor"),
    ("units_of_measure", "conversion_factor", "conversion_ratio"),
    ("accounts", "opening_balance", "balance"),
)


def _quote(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"unsafe identifier {name!r}")
    return name


def _pg_default(col, dialect: str = "postgresql") -> str | None:
    if col.server_default is not None:
        raw = getattr(col.server_default, "arg", None)
        if raw is not None and not callable(raw):
            return str(raw)
    default = col.default.arg if col.default is not None else None
    if callable(default):
        default = None
    if isinstance(col.type, Boolean):
        return "true" if default in {True, "true", "1", 1} else "false"
    if isinstance(col.type, (Integer, Numeric)):
        return "0" if default is None else str(default)
    if isinstance(col.type, JSON):
        return "'{}'" if dialect != "postgresql" else "'{}'::json"
    if isinstance(col.type, DateTime):
        return "CURRENT_TIMESTAMP"
    if isinstance(col.type, Date):
        return None
    if isinstance(col.type, (String, Text)):
        value = "trial" if col.name == "package_code" else (default if isinstance(default, str) else "")
        if col.name == "tax_supply_class":
            value = "standard"
        if col.name in {"decimal_separator"}:
            value = "."
        if col.name in {"thousand_separator"}:
            value = ","
        if col.name == "subscription_term_unit":
            return None
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"
    if default is True:
        return "true"
    if default is False:
        return "false"
    if isinstance(default, (int, float)):
        return str(default)
    return None


def _live_default(col_meta: dict) -> str | None:
    name = col_meta.get("name") or ""
    if name in {"reserved_qty", "minimum_stock", "balance", "opening_balance", "stock_qty"}:
        return "0"
    if name in {"conversion_factor", "conversion_ratio"}:
        return "1"
    if name in {"invoice_print_template"}:
        return "'a4'"
    if name in {"receipt_print_template"}:
        return "'thermal_80'"
    if name in {"plan_code"}:
        return "'trial'"
    if name in {"number_format"}:
        return "'1,234.56'"
    if name.startswith("is_") or name.endswith("_enabled"):
        return "false"
    if name.startswith("max_"):
        return "0"
    if name in {"smtp_use_tls"}:
        return "true"
    if name in {"smtp_use_ssl", "smtp_enabled"}:
        return "false"
    return None


def align_connection(sync_conn: Connection) -> None:
    dialect = sync_conn.dialect.name
    insp = inspect(sync_conn)
    tables = list(Base.metadata.tables.values())
    for table in tables:
        tname = table.name
        if not _IDENT.match(tname):
            continue
        if not insp.has_table(tname):
            continue
        live_cols = {c["name"]: c for c in insp.get_columns(tname)}
        for col in table.columns:
            if col.name in live_cols or not _IDENT.match(col.name):
                continue
            type_sql = col.type.compile(dialect=sync_conn.dialect)
            default = _pg_default(col, dialect)
            nullable = col.nullable
            if not nullable and default is None:
                default = _pg_default(col, dialect) or "NULL"
                if default == "NULL":
                    nullable = True
            pieces = [f"ALTER TABLE {_quote(tname)} ADD COLUMN"]
            if dialect == "postgresql":
                pieces.append("IF NOT EXISTS")
            pieces.append(f"{_quote(col.name)} {type_sql}")
            if default and default != "NULL":
                pieces.append(f"DEFAULT {default}")
            if nullable:
                pieces.append("NULL")
            else:
                pieces.append("NOT NULL")
            sql = " ".join(pieces)
            try:
                sync_conn.execute(text(sql))
                logger.info("schema align added %s.%s", tname, col.name)
            except Exception:
                logger.exception("schema align skip add %s.%s", tname, col.name)
        try:
            insp.clear_cache()
        except Exception:
            insp = inspect(sync_conn)
        live_cols = {c["name"]: c for c in insp.get_columns(tname)}
        mapped = {c.name for c in table.columns}
        for cname, cmeta in live_cols.items():
            if cname in mapped or not _IDENT.match(cname):
                continue
            if cmeta.get("nullable"):
                continue
            if cmeta.get("default") is not None:
                continue
            fallback = _live_default(cmeta)
            if not fallback:
                continue
            try:
                if dialect == "postgresql":
                    sync_conn.execute(
                        text(
                            f"ALTER TABLE {_quote(tname)} ALTER COLUMN {_quote(cname)} SET DEFAULT {fallback}"
                        )
                    )
                logger.info("schema align default %s.%s", tname, cname)
            except Exception:
                logger.exception("schema align skip default %s.%s", tname, cname)

    try:
        insp.clear_cache()
    except Exception:
        insp = inspect(sync_conn)
    for table_name, dest, src in _ALIAS_COPIES:
        if not insp.has_table(table_name):
            continue
        names = {c["name"] for c in insp.get_columns(table_name)}
        if dest not in names or src not in names:
            continue
        try:
            sync_conn.execute(
                text(
                    f"UPDATE {_quote(table_name)} SET {_quote(dest)} = {_quote(src)} "
                    f"WHERE {_quote(src)} IS NOT NULL AND "
                    f"({_quote(dest)} IS NULL OR CAST({_quote(dest)} AS TEXT) IN ('', 'trial', '0', '1'))"
                )
            )
        except Exception:
            logger.exception("schema align skip copy %s.%s <- %s", table_name, dest, src)


async def align_async_engine(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(align_connection)
    from app.schema_compat import clear_column_cache

    clear_column_cache()
