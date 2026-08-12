"""CSV export for cheques, POS sessions, and stock-count lists (Stage 130)."""

from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import cheques as cheques_svc
from app import pos as pos_svc
from app import stock_counts as stock_counts_svc
from app.session_passkey_doc_export import _cell

CHEQUE_EXPORT_COLUMNS = [
    "cheque_number",
    "direction",
    "status",
    "amount",
    "bank_name",
    "cheque_date",
    "party_id",
    "notes",
    "deposited_at",
    "cleared_at",
    "bounced_at",
    "created_at",
]

POS_SESSION_EXPORT_COLUMNS = [
    "session_number",
    "status",
    "store_id",
    "user_id",
    "opening_cash",
    "cash_sales",
    "card_sales",
    "other_sales",
    "total_sales",
    "sale_count",
    "expected_cash",
    "actual_cash",
    "variance",
    "opened_at",
    "closed_at",
    "notes",
]

STOCK_COUNT_EXPORT_COLUMNS = [
    "count_number",
    "status",
    "warehouse_id",
    "item_count",
    "counted_item_count",
    "notes",
    "created_by",
    "completed_by",
    "completed_at",
    "created_at",
]


async def export_cheques_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    direction: str | None = None,
    status: str | None = None,
) -> str:
    rows = await cheques_svc.list_cheques(
        db, tenant_id, direction=direction, status=status
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CHEQUE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = cheques_svc.serialize_cheque(row)
        writer.writerow({k: _cell(data.get(k)) for k in CHEQUE_EXPORT_COLUMNS})
    return buf.getvalue()


async def list_pos_sessions(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    limit: int = 50,
) -> list[m.PosSession]:
    q = select(m.PosSession).where(m.PosSession.tenant_id == tenant_id)
    status_n = (status or "").strip().lower() or None
    if status_n:
        q = q.where(m.PosSession.status == status_n)
    q = q.order_by(m.PosSession.opened_at.desc()).limit(min(max(limit, 1), 200))
    return list((await db.execute(q)).scalars().all())


async def export_pos_sessions_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
) -> str:
    rows = await list_pos_sessions(db, tenant_id=tenant_id, status=status, limit=200)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=POS_SESSION_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await pos_svc.serialize_session(row)
        writer.writerow({k: _cell(data.get(k)) for k in POS_SESSION_EXPORT_COLUMNS})
    return buf.getvalue()


async def list_stock_counts(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    limit: int = 50,
) -> list[m.StockCount]:
    q = select(m.StockCount).where(m.StockCount.tenant_id == tenant_id)
    status_n = (status or "").strip().lower() or None
    if status_n:
        q = q.where(m.StockCount.status == status_n)
    q = q.order_by(m.StockCount.created_at.desc()).limit(min(max(limit, 1), 200))
    return list((await db.execute(q)).scalars().all())


async def export_stock_counts_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
) -> str:
    rows = await list_stock_counts(db, tenant_id=tenant_id, status=status, limit=200)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=STOCK_COUNT_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = await stock_counts_svc.serialize_count(db, row)
        data.pop("items", None)
        writer.writerow({k: _cell(data.get(k)) for k in STOCK_COUNT_EXPORT_COLUMNS})
    return buf.getvalue()
