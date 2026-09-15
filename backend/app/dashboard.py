"""Dashboard KPIs: sales (today / MTD), purchases, expenses, stock alerts, AR/AP."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json


def _day_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def _month_start(d: date) -> datetime:
    return datetime(d.year, d.month, 1)


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    mo = (d.month - 1 + months) % 12 + 1
    return date(y, mo, 1)


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else 100.0
    return money_json(round((current - previous) / previous * 100.0, 1))


async def _sum_sales(
    db: AsyncSession,
    tenant_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    store_id: str | None = None,
) -> float:
    stmt = select(func.coalesce(func.sum(m.Transaction.total), 0.0)).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type.in_(["sale", "pos_sale"]),
    )
    if store_id:
        stmt = stmt.where(m.Transaction.store_id == store_id)
    if start is not None:
        stmt = stmt.where(m.Transaction.created_at >= start)
    if end is not None:
        stmt = stmt.where(m.Transaction.created_at < end)
    return money_json((await db.execute(stmt)).scalar_one())


async def build_dashboard(
    db: AsyncSession,
    tenant_id: str,
    *,
    store_id: str | None = None,
) -> dict[str, Any]:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    this_month = _month_start(today)
    next_month = _month_start(_add_months(today, 1))
    prev_month_start = _month_start(_add_months(today, -1))

    store_name: str | None = None
    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(m.Store.tenant_id == tenant_id, m.Store.id == store_id)
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        store_name = store.name

    async def scalar(stmt) -> Any:
        return (await db.execute(stmt)).scalar_one()

    sales_today = await _sum_sales(
        db, tenant_id, start=_day_start(today), end=_day_start(tomorrow), store_id=store_id
    )
    sales_yesterday = await _sum_sales(
        db, tenant_id, start=_day_start(yesterday), end=_day_start(today), store_id=store_id
    )
    sales_mtd = await _sum_sales(
        db, tenant_id, start=this_month, end=next_month, store_id=store_id
    )
    sales_prev_month = await _sum_sales(
        db, tenant_id, start=prev_month_start, end=this_month, store_id=store_id
    )

    purchases_stmt = select(func.coalesce(func.sum(m.Transaction.total), 0.0)).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "purchase",
        m.Transaction.created_at >= this_month,
        m.Transaction.created_at < next_month,
    )
    if store_id:
        purchases_stmt = purchases_stmt.where(m.Transaction.store_id == store_id)
    purchases_mtd = money_json(await scalar(purchases_stmt))

    expenses_stmt = select(func.coalesce(func.sum(m.Expense.amount), 0.0)).where(
        m.Expense.tenant_id == tenant_id,
        m.Expense.status == "approved",
        m.Expense.expense_date >= this_month,
        m.Expense.expense_date < next_month,
    )
    if store_id:
        expenses_stmt = expenses_stmt.where(m.Expense.store_id == store_id)
    expenses_mtd = money_json(await scalar(expenses_stmt))

    # Products at / below reorder (global product stock — not store-scoped bins).
    low_stock = (
        await db.execute(
            select(m.Product)
            .where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active.is_(True),
                m.Product.stock_qty <= m.Product.reorder_level,
            )
            .order_by(m.Product.stock_qty.asc())
            .limit(10)
        )
    ).scalars().all()

    # Expiring batches within 30 days.
    expiry_cut = datetime.utcnow() + timedelta(days=30)
    expiring = (
        await db.execute(
            select(m.ProductBatch, m.Product.name)
            .join(m.Product, m.Product.id == m.ProductBatch.product_id)
            .where(
                m.ProductBatch.tenant_id == tenant_id,
                m.ProductBatch.expiry_date.isnot(None),
                m.ProductBatch.expiry_date <= expiry_cut,
                m.ProductBatch.quantity > 0,
            )
            .order_by(m.ProductBatch.expiry_date.asc())
            .limit(10)
        )
    ).all()

    customers = await scalar(
        select(func.count()).select_from(m.Party).where(
            m.Party.tenant_id == tenant_id, m.Party.kind == "customer", m.Party.is_active.is_(True)
        )
    )
    suppliers = await scalar(
        select(func.count()).select_from(m.Party).where(
            m.Party.tenant_id == tenant_id, m.Party.kind == "supplier", m.Party.is_active.is_(True)
        )
    )
    products = await scalar(
        select(func.count()).select_from(m.Product).where(
            m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True)
        )
    )

    daily_sales_stmt = (
        select(m.Transaction)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type.in_(["sale", "pos_sale"]),
            m.Transaction.created_at >= this_month,
            m.Transaction.created_at < next_month,
        )
        .order_by(m.Transaction.created_at.asc())
    )
    if store_id:
        daily_sales_stmt = daily_sales_stmt.where(m.Transaction.store_id == store_id)
    daily_rows = (await db.execute(daily_sales_stmt)).scalars().all()
    by_day: dict[str, float] = {}
    for r in daily_rows:
        key = r.created_at.date().isoformat() if r.created_at else today.isoformat()
        by_day[key] = money_json(by_day.get(key, 0.0) + float(r.total or 0))
    # Fill every day of the month so charts don't jump.
    cursor = this_month.date()
    end_fill = min(today, (next_month - timedelta(seconds=1)).date())
    daily_series = []
    while cursor <= end_fill:
        k = cursor.isoformat()
        daily_series.append({"date": k, "sales": money_json(by_day.get(k, 0.0))})
        cursor += timedelta(days=1)

    # Top products this month from sale payloads (best-effort).
    product_totals: dict[str, dict[str, Any]] = {}
    for r in daily_rows:
        payload = r.payload or {}
        items = payload.get("items") or []
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or it.get("product_name") or "Item")
            qty = float(it.get("quantity") or it.get("qty") or 0)
            line = float(it.get("total") or it.get("line_total") or 0)
            if line == 0 and it.get("unit_price") is not None:
                line = float(it["unit_price"]) * qty
            bucket = product_totals.setdefault(name, {"name": name, "qty": 0.0, "revenue": 0.0})
            bucket["qty"] = money_json(bucket["qty"] + qty)
            bucket["revenue"] = money_json(bucket["revenue"] + line)
    top_products = sorted(product_totals.values(), key=lambda x: x["revenue"], reverse=True)[:5]

    recent_sales_stmt = (
        select(m.Transaction)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type.in_(["sale", "pos_sale"]),
        )
        .order_by(m.Transaction.created_at.desc())
        .limit(8)
    )
    if store_id:
        recent_sales_stmt = recent_sales_stmt.where(m.Transaction.store_id == store_id)
    recent_sales = (await db.execute(recent_sales_stmt)).scalars().all()

    return {
        "scope": "store" if store_id else "tenant",
        "store_id": store_id,
        "store_name": store_name,
        "as_of": datetime.utcnow().isoformat() + "Z",
        "kpis": {
            "sales_today": money_json(sales_today),
            "sales_yesterday": money_json(sales_yesterday),
            "sales_today_pct": _pct_change(sales_today, sales_yesterday),
            "sales_mtd": money_json(sales_mtd),
            "sales_prev_month": money_json(sales_prev_month),
            "sales_mtd_pct": _pct_change(sales_mtd, sales_prev_month),
            "purchases_mtd": money_json(purchases_mtd),
            "expenses_mtd": money_json(expenses_mtd),
            "customers": int(customers or 0),
            "suppliers": int(suppliers or 0),
            "products": int(products or 0),
            "low_stock_count": len(low_stock),
            "expiring_count": len(expiring),
        },
        "daily_sales": daily_series,
        "top_products": top_products,
        "low_stock": [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "stock_qty": money_json(p.stock_qty),
                "reorder_level": money_json(p.reorder_level),
            }
            for p in low_stock
        ],
        "expiring_batches": [
            {
                "batch_id": b.id,
                "product_id": b.product_id,
                "product_name": pname,
                "batch_number": b.batch_number,
                "expiry_date": b.expiry_date.isoformat() if b.expiry_date else None,
                "quantity": money_json(b.quantity),
            }
            for b, pname in expiring
        ],
        "recent_sales": [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "total": money_json(r.total),
                "payment_method": r.payment_method,
                "customer_name": (r.payload or {}).get("customer_name"),
            }
            for r in recent_sales
        ],
    }
