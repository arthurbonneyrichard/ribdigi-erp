"""Executive dashboard aggregates (BR-4.1 / 4.2 / 4.3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import tenants as tenants_svc
from app.config import settings


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return round((current - previous) / abs(previous) * 100.0, 1)


def _day_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1)


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


async def _sum_sales(
    db: AsyncSession,
    tenant_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> float:
    stmt = select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type.in_(["sale", "pos_sale"]),
    )
    if start is not None:
        stmt = stmt.where(m.Transaction.created_at >= start)
    if end is not None:
        stmt = stmt.where(m.Transaction.created_at < end)
    return float((await db.execute(stmt)).scalar() or 0)


async def build_dashboard(db: AsyncSession, tenant_id: str) -> dict[str, Any]:
    async def scalar(stmt):
        return (await db.execute(stmt)).scalar() or 0

    now_dt = datetime.utcnow()
    today = now_dt.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    this_month = _month_start(today.year, today.month)
    prev_y, prev_m = _add_months(today.year, today.month, -1)
    prev_month = _month_start(prev_y, prev_m)

    sales_all = await _sum_sales(db, tenant_id)
    sales_today = await _sum_sales(db, tenant_id, start=_day_start(today), end=_day_start(tomorrow))
    sales_yesterday = await _sum_sales(
        db, tenant_id, start=_day_start(yesterday), end=_day_start(today)
    )
    sales_mtd = await _sum_sales(db, tenant_id, start=this_month, end=_day_start(tomorrow))
    sales_prev_month = await _sum_sales(db, tenant_id, start=prev_month, end=this_month)

    purchases = float(
        await scalar(
            select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "purchase",
            )
        )
    )
    expenses = float(
        await scalar(
            select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
                m.Expense.tenant_id == tenant_id,
                m.Expense.status == "approved",
            )
        )
    )
    products = int(
        await scalar(select(func.count(m.Product.id)).where(m.Product.tenant_id == tenant_id))
    )
    low_stock = int(
        await scalar(
            select(func.count(m.Product.id)).where(
                m.Product.tenant_id == tenant_id,
                m.Product.stock_qty <= m.Product.reorder_level,
            )
        )
    )
    out_of_stock = int(
        await scalar(
            select(func.count(m.Product.id)).where(
                m.Product.tenant_id == tenant_id,
                m.Product.stock_qty <= 0,
            )
        )
    )
    customers = int(
        await scalar(
            select(func.count(m.Party.id)).where(
                m.Party.tenant_id == tenant_id, m.Party.kind == "customer"
            )
        )
    )
    suppliers = int(
        await scalar(
            select(func.count(m.Party.id)).where(
                m.Party.tenant_id == tenant_id, m.Party.kind == "supplier"
            )
        )
    )

    from app.catalog import list_expiring_batches

    expiring_batches = await list_expiring_batches(db, tenant_id, within_days=30)
    expiring_soon = len(expiring_batches)

    # Monthly sales trend (last 12 calendar months)
    months_seq = []
    for i in range(11, -1, -1):
        yy, mm = _add_months(now_dt.year, now_dt.month, -i)
        months_seq.append((yy, mm))
    earliest_month = _month_start(months_seq[0][0], months_seq[0][1])
    month_totals = {k: 0.0 for k in months_seq}
    trend_rows = (
        await db.execute(
            select(m.Transaction.created_at, m.Transaction.total).where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type.in_(["sale", "pos_sale"]),
                m.Transaction.created_at >= earliest_month,
            )
        )
    ).all()
    for created_at, total in trend_rows:
        if created_at is None:
            continue
        key = (created_at.year, created_at.month)
        if key in month_totals:
            month_totals[key] += float(total or 0)
    monthly_sales = [
        {
            "label": datetime(yy, mm, 1).strftime("%b %y"),
            "year": yy,
            "month": mm,
            "total": round(month_totals[(yy, mm)], 2),
        }
        for (yy, mm) in months_seq
    ]

    # Daily sales & profit for the last 30 days
    days_seq = [today - timedelta(days=i) for i in range(29, -1, -1)]
    earliest_day = _day_start(days_seq[0])
    cost_rows = (
        await db.execute(select(m.Product.id, m.Product.cost_price).where(m.Product.tenant_id == tenant_id))
    ).all()
    cost_map = {pid: float(cost or 0) for pid, cost in cost_rows}
    product_names = {
        pid: name
        for pid, name in (
            await db.execute(select(m.Product.id, m.Product.name).where(m.Product.tenant_id == tenant_id))
        ).all()
    }
    product_skus = {
        pid: sku
        for pid, sku in (
            await db.execute(select(m.Product.id, m.Product.sku).where(m.Product.tenant_id == tenant_id))
        ).all()
    }
    daily = {d: {"sales": 0.0, "profit": 0.0} for d in days_seq}
    top_qty: dict[str, float] = {}
    top_rev: dict[str, float] = {}
    daily_rows = (
        await db.execute(
            select(m.Transaction.created_at, m.Transaction.total, m.Transaction.payload).where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type.in_(["sale", "pos_sale"]),
                m.Transaction.created_at >= earliest_day,
            )
        )
    ).all()
    for created_at, total, payload in daily_rows:
        if created_at is None:
            continue
        d = created_at.date()
        if d in daily:
            daily[d]["sales"] += float(total or 0)
            for it in (payload or {}).get("items") or []:
                qty = float(it.get("quantity") or 0)
                unit_price = float(it.get("unit_price") or 0)
                pid = it.get("product_id")
                cost = cost_map.get(pid, 0.0)
                daily[d]["profit"] += qty * (unit_price - cost)
                if pid:
                    top_qty[pid] = top_qty.get(pid, 0.0) + qty
                    top_rev[pid] = top_rev.get(pid, 0.0) + qty * unit_price
    daily_sales = [
        {
            "label": d.strftime("%d %b"),
            "date": d.isoformat(),
            "sales": round(daily[d]["sales"], 2),
            "profit": round(daily[d]["profit"], 2),
        }
        for d in days_seq
    ]

    def _top(metric: dict[str, float], *, limit: int = 5) -> list[dict]:
        ranked = sorted(metric.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [
            {
                "product_id": pid,
                "name": product_names.get(pid) or pid,
                "sku": product_skus.get(pid),
                "quantity": round(top_qty.get(pid, 0.0), 2),
                "revenue": round(top_rev.get(pid, 0.0), 2),
            }
            for pid, _ in ranked
        ]

    top_products_by_revenue = _top(top_rev)
    top_products_by_quantity = _top(top_qty)

    recent_rows = (
        await db.execute(
            select(m.Transaction)
            .where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type.in_(["sale", "pos_sale"]),
            )
            .order_by(m.Transaction.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    recent_party_ids = [t.party_id for t in recent_rows if t.party_id]
    recent_party_names: dict = {}
    if recent_party_ids:
        recent_party_names = {
            p.id: p.name
            for p in (
                await db.execute(select(m.Party).where(m.Party.id.in_(recent_party_ids)))
            ).scalars().all()
        }
    recent_sales = [
        {
            "id": t.id,
            "reference": t.reference,
            "date": t.created_at,
            "total": float(t.total or 0),
            "customer": recent_party_names.get(t.party_id) or "Walk-in",
            "type": t.tx_type,
        }
        for t in recent_rows
    ]

    tenant = await db.get(m.Tenant, tenant_id)
    if tenant and tenant.status == "trial":
        days_remaining = tenants_svc.calendar_days_until(tenant.trial_ends_at)
    elif tenant and tenant.status == "grace":
        days_remaining = tenants_svc.calendar_days_until(tenant.grace_ends_at)
    else:
        days_remaining = None
    subscription = {
        "status": tenant.status if tenant else None,
        "trial_ends_at": tenant.trial_ends_at if tenant else None,
        "grace_ends_at": tenant.grace_ends_at if tenant else None,
        "days_remaining": days_remaining,
        "read_only": tenants_svc.is_read_only(tenant) if tenant else False,
        "trial_days": int(settings.TRIAL_DAYS),
    }

    return {
        "total_sales": sales_all,
        "total_purchases": purchases,
        "total_expenses": expenses,
        "products": products,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "expiring_soon": expiring_soon,
        "expiring_within_days": 30,
        "customers": customers,
        "suppliers": suppliers,
        "comparisons": {
            "sales_today": round(sales_today, 2),
            "sales_yesterday": round(sales_yesterday, 2),
            "sales_today_pct": _pct_change(sales_today, sales_yesterday),
            "sales_mtd": round(sales_mtd, 2),
            "sales_prev_month": round(sales_prev_month, 2),
            "sales_mtd_pct": _pct_change(sales_mtd, sales_prev_month),
        },
        "monthly_sales": monthly_sales,
        "daily_sales": daily_sales,
        "recent_sales": recent_sales,
        "top_products_by_revenue": top_products_by_revenue,
        "top_products_by_quantity": top_products_by_quantity,
        "links": {
            "sales": "/sales",
            "purchases": "/purchasing",
            "expenses": "/expenses",
            "customers": "/sales",
            "suppliers": "/purchasing",
            "products": "/inventory",
            "low_stock": "/reports",
            "expiring": "/inventory",
            "reports_sales": "/reports",
        },
        "subscription": subscription,
        "generated_at": now_dt,
    }
