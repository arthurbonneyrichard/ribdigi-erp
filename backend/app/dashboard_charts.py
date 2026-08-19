"""Executive dashboard sales visualization series (BR-4.3 / Stage 1 F16)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m


def _day_key(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d")


def _month_key(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.strftime("%Y-%m")


def fill_daily_series(
    amounts_by_day: dict[str, float],
    *,
    now: datetime,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Return last `days` calendar days ending today (inclusive), zero-filled."""
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days - 1)
    out: list[dict[str, Any]] = []
    cur = start
    while cur <= end:
        key = cur.strftime("%Y-%m-%d")
        out.append({"date": key, "revenue": round(float(amounts_by_day.get(key, 0.0)), 2)})
        cur += timedelta(days=1)
    return out


def fill_monthly_series(
    amounts_by_month: dict[str, float],
    *,
    now: datetime,
    months: int = 12,
) -> list[dict[str, Any]]:
    """Return last `months` calendar months ending this month, zero-filled."""
    y, mth = now.year, now.month
    keys: list[str] = []
    for _ in range(months):
        keys.append(f"{y:04d}-{mth:02d}")
        mth -= 1
        if mth == 0:
            mth = 12
            y -= 1
    keys.reverse()
    return [
        {"month": key, "revenue": round(float(amounts_by_month.get(key, 0.0)), 2)}
        for key in keys
    ]


async def load_revenue_chart_series(
    db: AsyncSession,
    *,
    tenant_id: str,
    now: datetime | None = None,
    store_ids: list[str] | None = None,
    company_id: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Aggregate POS/sale txs + posted invoices into daily (30d) and monthly (12m) series.

    When ``store_ids`` is provided (Stage 83 S1 Store Manager scope), only include
    invoices with matching ``store_id`` and POS txs via ``PosSession.store_id``.
    An empty list yields zero-filled series (manager with no stores).
    """
    now = now or datetime.utcnow()
    day_start = (now - timedelta(days=29)).replace(hour=0, minute=0, second=0, microsecond=0)
    # Start of the month 11 months before the current month (12 months inclusive).
    y, mth = now.year, now.month - 11
    while mth <= 0:
        mth += 12
        y -= 1
    month_horizon = datetime(y, mth, 1)

    daily: dict[str, float] = defaultdict(float)
    monthly: dict[str, float] = defaultdict(float)

    if store_ids is not None and len(store_ids) == 0:
        return {
            "daily_revenue_series": fill_daily_series(daily, now=now, days=30),
            "monthly_revenue_series": fill_monthly_series(monthly, now=now, months=12),
        }

    if store_ids is None:
        tx_q = select(m.Transaction.created_at, m.Transaction.total).where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type.in_(["sale", "pos_sale"]),
            m.Transaction.created_at >= month_horizon,
        )
        if company_id:
            tx_q = tx_q.where(m.Transaction.company_id == company_id)
        txs = (await db.execute(tx_q)).all()
    else:
        tx_q = (
            select(m.Transaction.created_at, m.Transaction.total)
            .select_from(m.Transaction)
            .join(m.PosSession, m.Transaction.session_id == m.PosSession.id)
            .where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type.in_(["sale", "pos_sale"]),
                m.Transaction.created_at >= month_horizon,
                m.PosSession.store_id.in_(store_ids),
            )
        )
        if company_id:
            tx_q = tx_q.where(m.Transaction.company_id == company_id)
        txs = (await db.execute(tx_q)).all()
    for created_at, total in txs:
        amt = float(total or 0)
        mk = _month_key(created_at)
        if mk:
            monthly[mk] += amt
        if created_at and created_at >= day_start:
            dk = _day_key(created_at)
            if dk:
                daily[dk] += amt

    inv_filters = [
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
        func.coalesce(m.SalesInvoice.posted_at, m.SalesInvoice.created_at) >= month_horizon,
    ]
    if store_ids is not None:
        inv_filters.append(m.SalesInvoice.store_id.in_(store_ids))
    if company_id:
        inv_filters.append(m.SalesInvoice.company_id == company_id)

    invs = (
        await db.execute(
            select(
                func.coalesce(m.SalesInvoice.posted_at, m.SalesInvoice.created_at),
                m.SalesInvoice.total_amount,
            ).where(*inv_filters)
        )
    ).all()
    for when, total in invs:
        amt = float(total or 0)
        mk = _month_key(when)
        if mk:
            monthly[mk] += amt
        if when and when >= day_start:
            dk = _day_key(when)
            if dk:
                daily[dk] += amt

    return {
        "daily_revenue_series": fill_daily_series(daily, now=now, days=30),
        "monthly_revenue_series": fill_monthly_series(monthly, now=now, months=12),
    }
