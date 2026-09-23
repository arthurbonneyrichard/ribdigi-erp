"""Insert/select using the live table columns so seed works across schema generations.

Production DBs may include main-line columns (company_id, is_system, parent_id)
and omit later production-only columns (opening_balance). ORM models must not
assume either set is present.
"""

from __future__ import annotations

from datetime import datetime
import re

from sqlalchemy import MetaData, Table, insert, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import uid

COLUMN_ALIASES = (
    ("conversion_ratio", "conversion_factor"),
    ("conversion_factor", "conversion_ratio"),
    ("account_type", "type"),
    ("rate", "percentage"),
)


def _python_type(col) -> type | None:
    try:
        return col.type.python_type
    except Exception:
        return None


def _slug_code(value: object) -> str:
    raw = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().upper()).strip("_")
    return (raw or "DEFAULT")[:40]


def _default_for_required_column(col, table_name: str = "", values: dict | None = None):
    name = col.name
    py = _python_type(col)
    values = values or {}
    if py is datetime:
        return datetime.utcnow()
    if py is bool or name.startswith("is_"):
        return name in {"is_active", "is_system", "is_default"}
    if py in {int, float} or name in {
        "balance",
        "opening_balance",
        "budget_amount",
        "discount_percent",
        "conversion_ratio",
        "conversion_factor",
        "rate",
        "percentage",
        "drawer_port",
    }:
        if name == "drawer_port":
            return 9100
        if name in {"conversion_ratio", "conversion_factor"}:
            return 1
        return 0
    if name == "status":
        return "unread" if table_name == "notifications" else "active"
    if name == "category" and table_name == "notifications":
        return "system"
    if name == "code":
        return _slug_code(values.get("code") or values.get("name") or table_name)
    if name == "tax_type":
        return "vat"
    if name == "pricing_mode":
        return "exclusive"
    if name == "industry":
        return "retail"
    if name == "currency":
        return "GHS"
    if name == "timezone":
        return "Africa/Accra"
    if name == "fiscal_year_start":
        return "01-01"
    if name == "invoice_print_template":
        return "a4"
    if name == "receipt_print_template":
        return "thermal_80"
    if name == "drawer_mode":
        return "none"
    if name == "warehouse_type":
        return "retail"
    if py is str:
        return "default"
    return None


def _session_connection(sync_session):
    """Use the session's transactional connection.

    Inspecting the engine bind can check out (or recycle) a pooled connection and
    roll back the open tenant-create transaction.
    """
    return sync_session.connection()


def _resolve_company_id(sync_session, tenant_id: str | None) -> str | None:
    if not tenant_id:
        return None
    conn = _session_connection(sync_session)
    insp = inspect(conn)
    if not insp.has_table("companies"):
        return None
    row = sync_session.execute(
        text("SELECT id FROM companies WHERE tenant_id = :tid LIMIT 1"),
        {"tid": tenant_id},
    ).first()
    return str(row[0]) if row and row[0] else None


def _prepare_payload(sync_session, table_name: str, values: dict) -> dict:
    tbl = Table(table_name, MetaData(), autoload_with=_session_connection(sync_session))
    payload = {key: value for key, value in values.items() if key in tbl.c}
    for src, dst in COLUMN_ALIASES:
        if src in values and dst in tbl.c and dst not in payload:
            payload[dst] = values[src]
    if "id" in tbl.c and "id" not in payload:
        payload["id"] = uid()
    if "company_id" in tbl.c and payload.get("company_id") in (None, ""):
        payload.pop("company_id", None)
        company_id = _resolve_company_id(sync_session, values.get("tenant_id"))
        if company_id:
            payload["company_id"] = company_id
    for col in tbl.columns:
        if col.name in payload:
            continue
        if col.nullable or col.primary_key:
            continue
        if col.default is not None or col.server_default is not None:
            continue
        filled = _default_for_required_column(col, table_name, values)
        if filled is not None:
            payload[col.name] = filled
    clean = {}
    for key, value in payload.items():
        col = tbl.c[key]
        if value is None and col.nullable:
            continue
        clean[key] = value
    if not clean:
        raise RuntimeError(f"no matching columns for {table_name}")
    return clean


async def table_column_names(db: AsyncSession, table_name: str) -> set[str]:
    def _names(sync_session) -> set[str]:
        insp = inspect(_session_connection(sync_session))
        if not insp.has_table(table_name):
            return set()
        return {c["name"] for c in insp.get_columns(table_name)}

    return await db.run_sync(_names)


async def insert_matching_row(db: AsyncSession, table_name: str, values: dict) -> None:
    def _insert(sync_session) -> None:
        payload = _prepare_payload(sync_session, table_name, values)
        tbl = Table(table_name, MetaData(), autoload_with=_session_connection(sync_session))
        sync_session.execute(insert(tbl).values(**payload))

    await db.run_sync(_insert)


async def existing_codes(db: AsyncSession, table_name: str, tenant_id: str, code_column: str = "code") -> set[str]:
    cols = await table_column_names(db, table_name)
    if code_column not in cols or "tenant_id" not in cols:
        return set()
    try:
        result = await db.execute(
            text(f"SELECT {code_column} FROM {table_name} WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        return {str(row[0]) for row in result if row[0] is not None}
    except Exception:
        return set()


async def existing_names(db: AsyncSession, table_name: str, tenant_id: str) -> set[str]:
    cols = await table_column_names(db, table_name)
    if "name" not in cols or "tenant_id" not in cols:
        return set()
    try:
        result = await db.execute(
            text(f"SELECT name FROM {table_name} WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        return {str(row[0]) for row in result if row[0] is not None}
    except Exception:
        return set()


async def resolve_tenant_company_id(db: AsyncSession, tenant_id: str) -> str | None:
    cols = await table_column_names(db, "companies")
    if not cols:
        return None
    try:
        existing = await db.execute(
            text("SELECT id FROM companies WHERE tenant_id = :tid LIMIT 1"),
            {"tid": tenant_id},
        )
        row = existing.first()
        return str(row[0]) if row and row[0] else None
    except Exception:
        return None


async def ensure_tenant_company(db: AsyncSession, tenant_id: str, *, name: str | None = None, industry: str | None = None, currency: str | None = None) -> str | None:
    cols = await table_column_names(db, "companies")
    if not cols:
        return None
    found = await resolve_tenant_company_id(db, tenant_id)
    if found:
        return found
    await insert_matching_row(
        db,
        "companies",
        {
            "tenant_id": tenant_id,
            "code": "MAIN",
            "name": (name or "Main").strip() or "Main",
            "industry": (industry or "retail").strip() or "retail",
            "currency": (currency or "GHS").strip() or "GHS",
            "timezone": "Africa/Accra",
            "fiscal_year_start": "01-01",
            "is_active": True,
            "is_default": True,
            "invoice_print_template": "a4",
            "receipt_print_template": "thermal_80",
            "store_limit": 5,
        },
    )
    await db.flush()
    return await resolve_tenant_company_id(db, tenant_id)
