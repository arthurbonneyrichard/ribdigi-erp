"""Insert/select using the live table columns so seed works across schema generations.

Production DBs may include main-line columns (company_id, is_system, parent_id)
and omit later production-only columns (opening_balance). ORM models must not
assume either set is present.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import MetaData, Table, insert, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import uid


def _python_type(col) -> type | None:
    try:
        return col.type.python_type
    except Exception:
        return None


def _default_for_required_column(col):
    name = col.name
    py = _python_type(col)
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
        "rate",
    }:
        return 0
    if name == "status":
        return "active"
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
    if "id" in tbl.c and "id" not in payload:
        payload["id"] = uid()
    if "company_id" in tbl.c and payload.get("company_id") in (None, ""):
        payload.pop("company_id", None)
        if not tbl.c.company_id.nullable:
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
        filled = _default_for_required_column(col)
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
    result = await db.execute(
        text(f"SELECT {code_column} FROM {table_name} WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    return {str(row[0]) for row in result if row[0] is not None}


async def existing_names(db: AsyncSession, table_name: str, tenant_id: str) -> set[str]:
    cols = await table_column_names(db, table_name)
    if "name" not in cols or "tenant_id" not in cols:
        return set()
    result = await db.execute(
        text(f"SELECT name FROM {table_name} WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    return {str(row[0]) for row in result if row[0] is not None}
