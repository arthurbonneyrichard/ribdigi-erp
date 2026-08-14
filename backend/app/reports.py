"""Operational and financial report aggregations."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m


def apply_company_filter(stmt, column, company_id: str | None):
    """Optionally narrow a report query to the active company workspace."""
    if company_id:
        return stmt.where(column == company_id)
    return stmt


def metric_change_pct(current: float, prior: float) -> float | None:
    """Percent change vs prior; ``None`` when prior is zero (same as sales comparative)."""
    if not prior:
        return None
    return round(((float(current) - float(prior)) / float(prior)) * 100, 2)


def prior_period_bounds(from_date: datetime, to_date: datetime) -> tuple[datetime, datetime]:
    """Equal-length period immediately before ``from_date``..``to_date`` (inclusive days)."""
    start = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_day = to_date.replace(hour=0, minute=0, second=0, microsecond=0)
    span_days = max((end_day - start).days + 1, 1)
    prior_end_day = start - timedelta(days=1)
    prior_start = prior_end_day - timedelta(days=span_days - 1)
    prior_end = prior_end_day.replace(hour=23, minute=59, second=59, microsecond=999999)
    return prior_start, prior_end


def prior_as_of_date(as_of: datetime) -> datetime:
    """Same calendar day one month earlier (day clamped to month length)."""
    y, m, d = as_of.year, as_of.month, as_of.day
    if m == 1:
        y, m = y - 1, 12
    else:
        m -= 1
    d = min(d, calendar.monthrange(y, m)[1])
    return as_of.replace(year=y, month=m, day=d)


def resolve_compare_period(
    from_date: datetime | None, to_date: datetime | None
) -> tuple[datetime, datetime]:
    """Effective current period for comparative reports (defaults to current calendar month)."""
    if from_date and to_date:
        start = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = to_date
        if end.hour == 0 and end.minute == 0 and end.second == 0 and end.microsecond == 0:
            end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end
    if to_date and not from_date:
        start, month_end = month_bounds(to_date.year, to_date.month)
        end = min(to_date, month_end)
        if end.hour == 0 and end.minute == 0 and end.second == 0:
            end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
        return start, end
    if from_date and not to_date:
        start = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
        _, month_end = month_bounds(from_date.year, from_date.month)
        return start, month_end
    now = datetime.utcnow()
    return month_bounds(now.year, now.month)


def build_comparison(
    *,
    mode: str,
    prior_meta: dict,
    current_metrics: dict[str, float],
    prior_metrics: dict[str, float],
) -> dict:
    metrics = {}
    for key, cur in current_metrics.items():
        pri = float(prior_metrics.get(key) or 0)
        cur_f = float(cur or 0)
        metrics[key] = {
            "current": cur_f,
            "prior": pri,
            "change_pct": metric_change_pct(cur_f, pri),
        }
    return {"mode": mode, **prior_meta, "metrics": metrics}


PNL_COMPARE_KEYS = (
    "revenue",
    "cogs",
    "gross_profit",
    "operating_expenses",
    "net_profit",
)
CASH_FLOW_COMPARE_KEYS = (
    "opening_cash",
    "closing_cash",
    "net_change",
    "inflows",
    "outflows",
)
BALANCE_SHEET_COMPARE_KEYS = (
    "total_assets",
    "total_liabilities",
    "total_equity",
    "total_liabilities_and_equity",
)


def _pick_metrics(payload: dict, keys: tuple[str, ...]) -> dict[str, float]:
    return {k: float(payload.get(k) or 0) for k in keys}


async def profit_loss_with_optional_compare(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    store_id: str | None = None,
    branch_id: str | None = None,
    compare: bool = False,
) -> dict:
    from app.accounting import profit_and_loss

    if not compare:
        return await profit_and_loss(
            db,
            tenant_id,
            from_date=from_date,
            to_date=to_date,
            store_id=store_id,
            branch_id=branch_id,
        )
    cur_from, cur_to = resolve_compare_period(from_date, to_date)
    prior_from, prior_to = prior_period_bounds(cur_from, cur_to)
    current = await profit_and_loss(
        db,
        tenant_id,
        from_date=cur_from,
        to_date=cur_to,
        store_id=store_id,
        branch_id=branch_id,
    )
    prior = await profit_and_loss(
        db,
        tenant_id,
        from_date=prior_from,
        to_date=prior_to,
        store_id=store_id,
        branch_id=branch_id,
    )
    current["comparison"] = build_comparison(
        mode="prior_period",
        prior_meta={
            "from_date": prior_from.date().isoformat(),
            "to_date": prior_to.date().isoformat(),
        },
        current_metrics=_pick_metrics(current, PNL_COMPARE_KEYS),
        prior_metrics=_pick_metrics(prior, PNL_COMPARE_KEYS),
    )
    return current


async def cash_flow_with_optional_compare(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    store_id: str | None = None,
    branch_id: str | None = None,
    compare: bool = False,
) -> dict:
    if not compare:
        return await cash_flow(
            db,
            tenant_id,
            from_date=from_date,
            to_date=to_date,
            store_id=store_id,
            branch_id=branch_id,
        )
    cur_from, cur_to = resolve_compare_period(from_date, to_date)
    prior_from, prior_to = prior_period_bounds(cur_from, cur_to)
    current = await cash_flow(
        db,
        tenant_id,
        from_date=cur_from,
        to_date=cur_to,
        store_id=store_id,
        branch_id=branch_id,
    )
    prior = await cash_flow(
        db,
        tenant_id,
        from_date=prior_from,
        to_date=prior_to,
        store_id=store_id,
        branch_id=branch_id,
    )
    current["comparison"] = build_comparison(
        mode="prior_period",
        prior_meta={
            "from_date": prior_from.date().isoformat(),
            "to_date": prior_to.date().isoformat(),
        },
        current_metrics=_pick_metrics(current, CASH_FLOW_COMPARE_KEYS),
        prior_metrics=_pick_metrics(prior, CASH_FLOW_COMPARE_KEYS),
    )
    return current


async def balance_sheet_with_optional_compare(
    db: AsyncSession,
    tenant_id: str,
    *,
    as_of: datetime | None,
    store_id: str | None = None,
    branch_id: str | None = None,
    compare: bool = False,
) -> dict:
    if not compare:
        return await balance_sheet(
            db, tenant_id, as_of=as_of, store_id=store_id, branch_id=branch_id
        )
    current_as_of = as_of or datetime.utcnow().replace(
        hour=23, minute=59, second=59, microsecond=999999
    )
    prior_as_of = prior_as_of_date(current_as_of)
    current = await balance_sheet(
        db,
        tenant_id,
        as_of=current_as_of,
        store_id=store_id,
        branch_id=branch_id,
    )
    prior = await balance_sheet(
        db,
        tenant_id,
        as_of=prior_as_of,
        store_id=store_id,
        branch_id=branch_id,
    )
    current["comparison"] = build_comparison(
        mode="prior_as_of",
        prior_meta={"as_of": prior_as_of.date().isoformat()},
        current_metrics=_pick_metrics(current, BALANCE_SHEET_COMPARE_KEYS),
        prior_metrics=_pick_metrics(prior, BALANCE_SHEET_COMPARE_KEYS),
    )
    return current


def parse_date(value: str | datetime | None, *, end_of_day: bool = False) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if len(text) == 10:
            dt = datetime.strptime(text, "%Y-%m-%d")
        else:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    if end_of_day:
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def day_bounds(day: datetime) -> tuple[datetime, datetime]:
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1) - timedelta(microseconds=1)
    return start, end


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year + 1, 1, 1) - timedelta(microseconds=1)
    else:
        end = datetime(year, month + 1, 1) - timedelta(microseconds=1)
    return start, end


def quarter_bounds(year: int, quarter: int) -> tuple[datetime, datetime]:
    if quarter not in (1, 2, 3, 4):
        raise ValueError("quarter must be 1–4")
    start_month = (quarter - 1) * 3 + 1
    start = datetime(year, start_month, 1)
    if quarter == 4:
        end = datetime(year + 1, 1, 1) - timedelta(microseconds=1)
    else:
        end = datetime(year, start_month + 3, 1) - timedelta(microseconds=1)
    return start, end


def year_bounds(year: int) -> tuple[datetime, datetime]:
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1) - timedelta(microseconds=1)
    return start, end


def resolve_report_period(
    *,
    period: str | None = None,
    year: int | None = None,
    month: int | None = None,
    quarter: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    ref: datetime | None = None,
) -> tuple[datetime | None, datetime | None, dict]:
    """Resolve monthly/quarterly/annual bounds or explicit from/to dates (Stage 14 T1)."""
    from fastapi import HTTPException

    ref_dt = ref or datetime.utcnow()
    meta: dict = {
        "period": None,
        "year": None,
        "month": None,
        "quarter": None,
    }
    if period:
        kind = period.strip().lower()
        if kind in {"month", "monthly"}:
            y = int(year or ref_dt.year)
            m = int(month or ref_dt.month)
            if m < 1 or m > 12:
                raise HTTPException(status_code=400, detail="month must be 1–12")
            start, end = month_bounds(y, m)
            meta.update({"period": "monthly", "year": y, "month": m})
            return start, end, meta
        if kind in {"quarter", "quarterly"}:
            y = int(year or ref_dt.year)
            if quarter is None:
                q = (ref_dt.month - 1) // 3 + 1
            else:
                q = int(quarter)
            if q not in (1, 2, 3, 4):
                raise HTTPException(status_code=400, detail="quarter must be 1–4")
            start, end = quarter_bounds(y, q)
            meta.update({"period": "quarterly", "year": y, "quarter": q})
            return start, end, meta
        if kind in {"year", "annual", "annually"}:
            y = int(year or ref_dt.year)
            start, end = year_bounds(y)
            meta.update({"period": "annually", "year": y})
            return start, end, meta
        raise HTTPException(
            status_code=400,
            detail="period must be monthly, quarterly, or annually",
        )
    return parse_date(from_date), parse_date(to_date, end_of_day=True), meta


async def _sales_totals_for_bounds(
    db: AsyncSession,
    tenant_id: str,
    start: datetime,
    end: datetime,
    *,
    company_id: str | None = None,
) -> dict:
    inv_q = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
        m.SalesInvoice.posted_at >= start,
        m.SalesInvoice.posted_at <= end,
    )
    pos_q = select(m.Transaction).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
        m.Transaction.created_at >= start,
        m.Transaction.created_at <= end,
    )
    if company_id:
        inv_q = inv_q.where(m.SalesInvoice.company_id == company_id)
        pos_q = pos_q.where(m.Transaction.company_id == company_id)
    invoices = (await db.execute(inv_q)).scalars().all()
    pos = (await db.execute(pos_q)).scalars().all()
    invoice_total = sum(float(i.total_amount or 0) for i in invoices)
    invoice_tax = sum(float(i.tax_amount or 0) for i in invoices)
    invoice_discount = sum(float(i.discount_amount or 0) for i in invoices)
    pos_total = sum(float(t.total or 0) for t in pos)
    pos_tax = sum(float(t.tax or 0) for t in pos)
    total = invoice_total + pos_total
    return {
        "invoice_count": len(invoices),
        "pos_count": len(pos),
        "invoice_revenue": round(invoice_total, 2),
        "pos_revenue": round(pos_total, 2),
        "total_revenue": round(total, 2),
        "tax": round(invoice_tax + pos_tax, 2),
        "discounts": round(invoice_discount, 2),
        "net_sales": round(total - invoice_discount, 2),
    }


async def sales_daily(
    db: AsyncSession,
    tenant_id: str,
    date: datetime | None = None,
    *,
    company_id: str | None = None,
) -> dict:
    day = date or datetime.utcnow()
    start, end = day_bounds(day)
    current = await _sales_totals_for_bounds(
        db, tenant_id, start, end, company_id=company_id
    )
    prev_start, prev_end = day_bounds(start - timedelta(days=1))
    previous = await _sales_totals_for_bounds(
        db, tenant_id, prev_start, prev_end, company_id=company_id
    )
    prev_rev = float(previous["total_revenue"] or 0)
    cur_rev = float(current["total_revenue"] or 0)
    return {
        "date": start.date().isoformat(),
        **current,
        "previous_date": prev_start.date().isoformat(),
        "previous_day_revenue": prev_rev,
        "change_pct": round(((cur_rev - prev_rev) / prev_rev) * 100, 2) if prev_rev else None,
    }


async def sales_monthly(
    db: AsyncSession,
    tenant_id: str,
    year: int,
    month: int,
    *,
    company_id: str | None = None,
) -> dict:
    start, end = month_bounds(year, month)
    inv_q = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
        m.SalesInvoice.posted_at >= start,
        m.SalesInvoice.posted_at <= end,
    )
    inv_q = apply_company_filter(inv_q, m.SalesInvoice.company_id, company_id)
    invoices = (await db.execute(inv_q)).scalars().all()
    pos_q = select(m.Transaction).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
        m.Transaction.created_at >= start,
        m.Transaction.created_at <= end,
    )
    pos_q = apply_company_filter(pos_q, m.Transaction.company_id, company_id)
    pos = (await db.execute(pos_q)).scalars().all()

    by_day: dict[str, float] = defaultdict(float)
    for inv in invoices:
        key = (inv.posted_at or inv.created_at).date().isoformat()
        by_day[key] += float(inv.total_amount or 0)
    for tx in pos:
        key = tx.created_at.date().isoformat()
        by_day[key] += float(tx.total or 0)

    total = sum(by_day.values())
    prev_year, prev_month = (year - 1, month) if month == 1 else (year, month - 1)
    prev = await sales_monthly_total(
        db, tenant_id, prev_year, prev_month, company_id=company_id
    )
    return {
        "year": year,
        "month": month,
        "invoice_count": len(invoices),
        "pos_count": len(pos),
        "total_revenue": round(total, 2),
        "previous_month_revenue": prev,
        "change_pct": round(((total - prev) / prev) * 100, 2) if prev else None,
        "daily": [{"date": d, "revenue": round(v, 2)} for d, v in sorted(by_day.items())],
    }


async def sales_monthly_total(
    db: AsyncSession,
    tenant_id: str,
    year: int,
    month: int,
    *,
    company_id: str | None = None,
) -> float:
    start, end = month_bounds(year, month)
    inv_q = select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
        m.SalesInvoice.posted_at >= start,
        m.SalesInvoice.posted_at <= end,
    )
    inv_q = apply_company_filter(inv_q, m.SalesInvoice.company_id, company_id)
    inv = float((await db.execute(inv_q)).scalar() or 0)
    pos_q = select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
        m.Transaction.created_at >= start,
        m.Transaction.created_at <= end,
    )
    pos_q = apply_company_filter(pos_q, m.Transaction.company_id, company_id)
    pos = float((await db.execute(pos_q)).scalar() or 0)
    return round(inv + pos, 2)


async def sales_by_product(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    category_id: str | None = None,
    company_id: str | None = None,
) -> dict:
    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(m.Store.id == store_id, m.Store.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not store:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Store not found")
    if category_id:
        cat = (
            await db.execute(
                select(m.ProductCategory).where(
                    m.ProductCategory.id == category_id,
                    m.ProductCategory.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not cat:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Category not found")

    stmt = select(m.SalesInvoiceItem, m.SalesInvoice, m.Product).join(
        m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id
    ).join(m.Product, m.Product.id == m.SalesInvoiceItem.product_id).where(
        m.SalesInvoiceItem.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
    )
    stmt = apply_company_filter(stmt, m.SalesInvoice.company_id, company_id)
    if from_date:
        stmt = stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        stmt = stmt.where(m.SalesInvoice.posted_at <= to_date)
    if store_id:
        stmt = stmt.where(m.SalesInvoice.store_id == store_id)
    if category_id:
        stmt = stmt.where(m.Product.category_id == category_id)
    rows = (await db.execute(stmt)).all()

    agg: dict[str, dict] = {}
    for item, _inv, product in rows:
        row = agg.setdefault(
            product.id,
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "category_id": getattr(product, "category_id", None),
                "quantity": 0.0,
                "revenue": 0.0,
            },
        )
        row["quantity"] = round(row["quantity"] + float(item.quantity or 0), 3)
        row["revenue"] = round(row["revenue"] + float(item.line_total or 0), 2)

    # Include POS payload items where possible
    pos_stmt = select(m.Transaction, m.PosSession).outerjoin(
        m.PosSession, m.PosSession.id == m.Transaction.session_id
    ).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
    )
    pos_stmt = apply_company_filter(pos_stmt, m.Transaction.company_id, company_id)
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    if store_id:
        pos_stmt = pos_stmt.where(m.PosSession.store_id == store_id)
    for tx, _session in (await db.execute(pos_stmt)).all():
        for line in (tx.payload or {}).get("items") or []:
            pid = line.get("product_id")
            if not pid:
                continue
            product = await db.get(m.Product, pid)
            if not product or product.tenant_id != tenant_id:
                continue
            if category_id and getattr(product, "category_id", None) != category_id:
                continue
            row = agg.setdefault(
                product.id,
                {
                    "product_id": product.id,
                    "sku": product.sku,
                    "name": product.name,
                    "category_id": getattr(product, "category_id", None),
                    "quantity": 0.0,
                    "revenue": 0.0,
                },
            )
            qty = float(line.get("quantity") or 0)
            revenue = float(line.get("line_total") or (float(line.get("unit_price") or product.selling_price or 0) * qty))
            row["quantity"] = round(row["quantity"] + qty, 3)
            row["revenue"] = round(row["revenue"] + revenue, 2)

    products = sorted(agg.values(), key=lambda x: x["revenue"], reverse=True)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "store_id": store_id,
        "category_id": category_id,
        "products": products,
        "total_revenue": round(sum(p["revenue"] for p in products), 2),
        "total_quantity": round(sum(p["quantity"] for p in products), 3),
    }


async def sales_by_customer(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 50,
    company_id: str | None = None,
) -> dict:
    """Top customers by revenue and purchase frequency (BR-14.1)."""
    limit = max(1, min(int(limit or 50), 200))

    def _bucket(agg: dict[str, dict], customer_id: str | None) -> dict:
        key = customer_id or "walk_in"
        return agg.setdefault(
            key,
            {
                "customer_id": None if key == "walk_in" else key,
                "name": "Walk-in",
                "code": None,
                "sale_count": 0,
                "invoice_count": 0,
                "pos_count": 0,
                "revenue": 0.0,
                "tax": 0.0,
                "avg_ticket": 0.0,
            },
        )

    agg: dict[str, dict] = {}
    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid", "sent", "overdue"]),
    )
    inv_stmt = apply_company_filter(inv_stmt, m.SalesInvoice.company_id, company_id)
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    for inv in (await db.execute(inv_stmt)).scalars().all():
        row = _bucket(agg, inv.customer_id)
        row["invoice_count"] += 1
        row["sale_count"] += 1
        row["revenue"] = round(row["revenue"] + float(inv.total_amount or 0), 2)
        row["tax"] = round(row["tax"] + float(inv.tax_amount or 0), 2)

    pos_stmt = select(m.Transaction).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
    )
    pos_stmt = apply_company_filter(pos_stmt, m.Transaction.company_id, company_id)
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    for tx in (await db.execute(pos_stmt)).scalars().all():
        row = _bucket(agg, tx.party_id)
        row["pos_count"] += 1
        row["sale_count"] += 1
        row["revenue"] = round(row["revenue"] + float(tx.total or 0), 2)
        row["tax"] = round(row["tax"] + float(tx.tax or 0), 2)

    party_ids = [k for k in agg.keys() if k != "walk_in"]
    if party_ids:
        parties = (
            await db.execute(
                select(m.Party).where(
                    m.Party.tenant_id == tenant_id,
                    m.Party.id.in_(party_ids),
                )
            )
        ).scalars().all()
        by_id = {p.id: p for p in parties}
        for key in party_ids:
            party = by_id.get(key)
            if party:
                agg[key]["name"] = party.name
                agg[key]["code"] = getattr(party, "code", None)

    for row in agg.values():
        row["avg_ticket"] = round(row["revenue"] / row["sale_count"], 2) if row["sale_count"] else 0.0

    customers = sorted(agg.values(), key=lambda x: (x["revenue"], x["sale_count"]), reverse=True)
    # Prefer named customers ahead of empty walk-in when revenue ties at zero
    if customers and customers[0]["customer_id"] is None and customers[0]["sale_count"] == 0:
        customers = customers[1:]
    customers = customers[:limit]
    return {
        "from_date": from_date,
        "to_date": to_date,
        "customers": customers,
        "total_revenue": round(sum(c["revenue"] for c in customers), 2),
        "total_sales": sum(c["sale_count"] for c in customers),
        "customer_count": len(customers),
    }


async def sales_by_salesperson(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    company_id: str | None = None,
) -> dict:
    """Aggregate posted invoices + POS sales by salesperson (invoice created_by / POS session user)."""

    def _bucket(agg: dict[str, dict], user_id: str | None) -> dict:
        key = user_id or "unknown"
        return agg.setdefault(
            key,
            {
                "user_id": None if key == "unknown" else key,
                "full_name": "Unknown",
                "email": None,
                "role": None,
                "invoice_count": 0,
                "invoice_revenue": 0.0,
                "invoice_tax": 0.0,
                "pos_count": 0,
                "pos_revenue": 0.0,
                "pos_tax": 0.0,
                "sale_count": 0,
                "revenue": 0.0,
                "tax": 0.0,
                "avg_ticket": 0.0,
            },
        )

    agg: dict[str, dict] = {}

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
    )
    inv_stmt = apply_company_filter(inv_stmt, m.SalesInvoice.company_id, company_id)
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    for inv in (await db.execute(inv_stmt)).scalars().all():
        row = _bucket(agg, inv.created_by)
        total = float(inv.total_amount or 0)
        tax = float(inv.tax_amount or 0)
        row["invoice_count"] += 1
        row["invoice_revenue"] = round(row["invoice_revenue"] + total, 2)
        row["invoice_tax"] = round(row["invoice_tax"] + tax, 2)
        row["sale_count"] += 1
        row["revenue"] = round(row["revenue"] + total, 2)
        row["tax"] = round(row["tax"] + tax, 2)

    pos_stmt = (
        select(m.Transaction, m.PosSession)
        .outerjoin(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
        )
    )
    pos_stmt = apply_company_filter(pos_stmt, m.Transaction.company_id, company_id)
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    for tx, session in (await db.execute(pos_stmt)).all():
        user_id = session.user_id if session else None
        row = _bucket(agg, user_id)
        total = float(tx.total or 0)
        tax = float(tx.tax or 0)
        row["pos_count"] += 1
        row["pos_revenue"] = round(row["pos_revenue"] + total, 2)
        row["pos_tax"] = round(row["pos_tax"] + tax, 2)
        row["sale_count"] += 1
        row["revenue"] = round(row["revenue"] + total, 2)
        row["tax"] = round(row["tax"] + tax, 2)

    user_ids = [k for k in agg.keys() if k != "unknown"]
    if user_ids:
        users = (
            await db.execute(
                select(m.User).where(
                    m.User.tenant_id == tenant_id,
                    m.User.id.in_(user_ids),
                )
            )
        ).scalars().all()
        by_id = {u.id: u for u in users}
        for key, row in agg.items():
            if key == "unknown":
                continue
            user = by_id.get(key)
            if user:
                row["full_name"] = user.full_name
                row["email"] = user.email
                row["role"] = user.role

    for row in agg.values():
        row["avg_ticket"] = round(row["revenue"] / row["sale_count"], 2) if row["sale_count"] else 0.0

    salespeople = sorted(agg.values(), key=lambda x: x["revenue"], reverse=True)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "salespeople": salespeople,
        "total_revenue": round(sum(s["revenue"] for s in salespeople), 2),
        "total_sales": sum(s["sale_count"] for s in salespeople),
        "invoice_revenue": round(sum(s["invoice_revenue"] for s in salespeople), 2),
        "pos_revenue": round(sum(s["pos_revenue"] for s in salespeople), 2),
    }


async def sales_by_store(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    company_id: str | None = None,
) -> dict:
    """Aggregate posted invoices + POS sales by store (invoice.store_id / POS session.store_id)."""

    def _bucket(agg: dict[str, dict], store_id: str | None) -> dict:
        key = store_id or "unknown"
        return agg.setdefault(
            key,
            {
                "store_id": None if key == "unknown" else key,
                "name": "Unassigned",
                "code": None,
                "invoice_count": 0,
                "invoice_revenue": 0.0,
                "invoice_tax": 0.0,
                "pos_count": 0,
                "pos_revenue": 0.0,
                "pos_tax": 0.0,
                "sale_count": 0,
                "revenue": 0.0,
                "tax": 0.0,
                "avg_ticket": 0.0,
            },
        )

    agg: dict[str, dict] = {}

    # Seed active stores so zero-activity locations still appear.
    store_q = select(m.Store).where(m.Store.tenant_id == tenant_id).order_by(m.Store.name)
    store_q = apply_company_filter(store_q, m.Store.company_id, company_id)
    stores = (await db.execute(store_q)).scalars().all()
    for store in stores:
        row = _bucket(agg, store.id)
        row["name"] = store.name
        row["code"] = store.code

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
    )
    inv_stmt = apply_company_filter(inv_stmt, m.SalesInvoice.company_id, company_id)
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    for inv in (await db.execute(inv_stmt)).scalars().all():
        row = _bucket(agg, inv.store_id)
        total = float(inv.total_amount or 0)
        tax = float(inv.tax_amount or 0)
        row["invoice_count"] += 1
        row["invoice_revenue"] = round(row["invoice_revenue"] + total, 2)
        row["invoice_tax"] = round(row["invoice_tax"] + tax, 2)
        row["sale_count"] += 1
        row["revenue"] = round(row["revenue"] + total, 2)
        row["tax"] = round(row["tax"] + tax, 2)

    pos_stmt = (
        select(m.Transaction, m.PosSession)
        .outerjoin(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
        )
    )
    pos_stmt = apply_company_filter(pos_stmt, m.Transaction.company_id, company_id)
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    for tx, session in (await db.execute(pos_stmt)).all():
        store_id = session.store_id if session else None
        row = _bucket(agg, store_id)
        total = float(tx.total or 0)
        tax = float(tx.tax or 0)
        row["pos_count"] += 1
        row["pos_revenue"] = round(row["pos_revenue"] + total, 2)
        row["pos_tax"] = round(row["pos_tax"] + tax, 2)
        row["sale_count"] += 1
        row["revenue"] = round(row["revenue"] + total, 2)
        row["tax"] = round(row["tax"] + tax, 2)

    # Enrich store rows that came only from activity (not in seed list).
    orphan_ids = [k for k in agg.keys() if k != "unknown" and agg[k]["code"] is None]
    if orphan_ids:
        found = (
            await db.execute(
                select(m.Store).where(
                    m.Store.tenant_id == tenant_id,
                    m.Store.id.in_(orphan_ids),
                )
            )
        ).scalars().all()
        by_id = {s.id: s for s in found}
        for key in orphan_ids:
            store = by_id.get(key)
            if store:
                agg[key]["name"] = store.name
                agg[key]["code"] = store.code
            else:
                agg[key]["name"] = f"Store {key[:8]}"

    for row in agg.values():
        row["avg_ticket"] = round(row["revenue"] / row["sale_count"], 2) if row["sale_count"] else 0.0

    # Drop pure zero rows for unknown only if empty; keep real stores even at zero.
    stores_out = []
    for key, row in agg.items():
        if key == "unknown" and row["sale_count"] == 0:
            continue
        stores_out.append(row)
    stores_out.sort(key=lambda x: x["revenue"], reverse=True)

    return {
        "from_date": from_date,
        "to_date": to_date,
        "stores": stores_out,
        "total_revenue": round(sum(s["revenue"] for s in stores_out), 2),
        "total_sales": sum(s["sale_count"] for s in stores_out),
        "invoice_revenue": round(sum(s["invoice_revenue"] for s in stores_out), 2),
        "pos_revenue": round(sum(s["pos_revenue"] for s in stores_out), 2),
    }


async def inventory_balance(
    db: AsyncSession,
    tenant_id: str,
    warehouse_id: str | None = None,
    *,
    company_id: str | None = None,
) -> dict:
    if warehouse_id:
        stmt = (
            select(m.WarehouseStock, m.Product)
            .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
            .where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == warehouse_id,
            )
            .order_by(m.Product.name)
        )
        stmt = apply_company_filter(stmt, m.WarehouseStock.company_id, company_id)
        rows = (await db.execute(stmt)).all()
        items = [
            {
                "product_id": p.id,
                "sku": p.sku,
                "name": p.name,
                "warehouse_id": warehouse_id,
                "quantity": float(s.quantity or 0),
                "cost_price": float(p.cost_price or 0),
                "value": round(float(s.quantity or 0) * float(p.cost_price or 0), 2),
            }
            for s, p in rows
        ]
    else:
        pq = select(m.Product).where(
            m.Product.tenant_id == tenant_id, m.Product.is_active == True  # noqa: E712
        ).order_by(m.Product.name)
        pq = apply_company_filter(pq, m.Product.company_id, company_id)
        products = (await db.execute(pq)).scalars().all()
        items = [
            {
                "product_id": p.id,
                "sku": p.sku,
                "name": p.name,
                "warehouse_id": None,
                "quantity": float(p.stock_qty or 0),
                "cost_price": float(p.cost_price or 0),
                "value": round(float(p.stock_qty or 0) * float(p.cost_price or 0), 2),
            }
            for p in products
        ]
    return {
        "warehouse_id": warehouse_id,
        "items": items,
        "total_quantity": round(sum(i["quantity"] for i in items), 3),
        "total_value": round(sum(i["value"] for i in items), 2),
    }


async def inventory_valuation(
    db: AsyncSession,
    tenant_id: str,
    *,
    warehouse_id: str | None = None,
    store_id: str | None = None,
    company_id: str | None = None,
) -> dict:
    """Stock valuation at standard cost: quantity × product.cost_price (Stage 9 R2).

    FIFO, LIFO, and weighted-average layer costing are intentionally out of scope.
    """
    from app import stores as stores_svc

    resolved_warehouse_id = warehouse_id
    if store_id and not warehouse_id:
        wh = await stores_svc.warehouse_for_store(db, tenant_id, store_id)
        resolved_warehouse_id = wh.id

    stmt = (
        select(m.WarehouseStock, m.Product, m.Warehouse)
        .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
        .join(m.Warehouse, m.Warehouse.id == m.WarehouseStock.warehouse_id)
        .where(m.WarehouseStock.tenant_id == tenant_id)
        .order_by(m.Warehouse.code, m.Product.name)
    )
    if company_id:
        stmt = stmt.where(m.Warehouse.company_id == company_id)
    if resolved_warehouse_id:
        stmt = stmt.where(m.WarehouseStock.warehouse_id == resolved_warehouse_id)
    rows = (await db.execute(stmt)).all()

    items: list[dict] = []
    by_wh: dict[str, dict] = {}
    for stock, product, warehouse in rows:
        qty = float(stock.quantity or 0)
        cost = float(product.cost_price or 0)
        value = round(qty * cost, 2)
        items.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "warehouse_id": warehouse.id,
                "warehouse_code": warehouse.code,
                "warehouse_name": warehouse.name,
                "quantity": qty,
                "cost_price": cost,
                "value": value,
            }
        )
        bucket = by_wh.setdefault(
            warehouse.id,
            {
                "warehouse_id": warehouse.id,
                "warehouse_code": warehouse.code,
                "warehouse_name": warehouse.name,
                "line_count": 0,
                "total_quantity": 0.0,
                "total_value": 0.0,
            },
        )
        bucket["line_count"] += 1
        bucket["total_quantity"] = round(bucket["total_quantity"] + qty, 3)
        bucket["total_value"] = round(bucket["total_value"] + value, 2)

    # Fallback when tenant stock lives only on product.stock_qty (no warehouse rows yet).
    if not items and not resolved_warehouse_id:
        products = (
            await db.execute(
                select(m.Product)
                .where(m.Product.tenant_id == tenant_id, m.Product.is_active == True)  # noqa: E712
                .order_by(m.Product.name)
            )
        ).scalars().all()
        for product in products:
            qty = float(product.stock_qty or 0)
            if qty == 0:
                continue
            cost = float(product.cost_price or 0)
            items.append(
                {
                    "product_id": product.id,
                    "sku": product.sku,
                    "name": product.name,
                    "warehouse_id": None,
                    "warehouse_code": None,
                    "warehouse_name": None,
                    "quantity": qty,
                    "cost_price": cost,
                    "value": round(qty * cost, 2),
                }
            )

    by_warehouse = sorted(by_wh.values(), key=lambda x: x["warehouse_code"] or "")
    return {
        "costing_method": "standard_cost",
        "costing_method_note": (
            "Value = quantity × product.cost_price. "
            "FIFO, LIFO, and weighted average are not used in commercial MVP."
        ),
        "warehouse_id": resolved_warehouse_id,
        "store_id": store_id,
        "items": items,
        "by_warehouse": by_warehouse,
        "total_quantity": round(sum(i["quantity"] for i in items), 3),
        "total_value": round(sum(i["value"] for i in items), 2),
        "line_count": len(items),
    }


async def inventory_movements(
    db: AsyncSession,
    tenant_id: str,
    *,
    product_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 200,
    company_id: str | None = None,
) -> dict:
    stmt = select(m.StockMovement).where(m.StockMovement.tenant_id == tenant_id)
    stmt = apply_company_filter(stmt, m.StockMovement.company_id, company_id)
    if product_id:
        stmt = stmt.where(m.StockMovement.product_id == product_id)
    if from_date:
        stmt = stmt.where(m.StockMovement.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.StockMovement.created_at <= to_date)
    stmt = stmt.order_by(m.StockMovement.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "count": len(rows),
        "movements": [
            {
                "id": r.id,
                "product_id": r.product_id,
                "warehouse_id": r.warehouse_id,
                "movement_type": r.movement_type,
                "quantity": float(r.quantity),
                "quantity_before": float(r.quantity_before),
                "quantity_after": float(r.quantity_after),
                "reference_type": r.reference_type,
                "reference_id": r.reference_id,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


async def inventory_low_stock(
    db: AsyncSession,
    tenant_id: str,
    *,
    store_id: str | None = None,
    warehouse_id: str | None = None,
    company_id: str | None = None,
) -> dict:
    """Product-level and optional store/warehouse reorder breaches."""
    from app.inventory import compute_stock_status

    pq = select(m.Product).where(
        m.Product.tenant_id == tenant_id,
        m.Product.is_active == True,  # noqa: E712
    ).order_by(m.Product.stock_qty.asc())
    pq = apply_company_filter(pq, m.Product.company_id, company_id)
    products = (await db.execute(pq)).scalars().all()
    product_rows = []
    for p in products:
        qty = float(p.stock_qty or 0)
        minimum = float(getattr(p, "minimum_stock", 0) or 0)
        reorder = float(p.reorder_level or 0)
        status = compute_stock_status(qty, minimum, reorder)
        if status == "green":
            continue
        product_rows.append(
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "stock_qty": qty,
                "minimum_stock": minimum,
                "reorder_level": reorder,
                "stock_status": status,
                "scope": "product",
            }
        )

    wh_filter = warehouse_id
    store = None
    if store_id and not wh_filter:
        from app import stores as stores_svc

        store = await stores_svc.get_store(db, tenant_id, store_id)
        wh = await stores_svc.warehouse_for_store(db, tenant_id, store_id)
        wh_filter = wh.id

    warehouse_rows: list[dict] = []
    stmt = (
        select(m.WarehouseStock, m.Product, m.Warehouse)
        .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
        .join(m.Warehouse, m.Warehouse.id == m.WarehouseStock.warehouse_id)
        .where(
            m.WarehouseStock.tenant_id == tenant_id,
            (m.WarehouseStock.reorder_level > 0) | (m.WarehouseStock.minimum_stock > 0),
        )
        .order_by(m.WarehouseStock.quantity.asc())
    )
    stmt = apply_company_filter(stmt, m.Warehouse.company_id, company_id)
    if wh_filter:
        stmt = stmt.where(m.WarehouseStock.warehouse_id == wh_filter)
    from app.inventory import compute_stock_status, effective_warehouse_thresholds

    for stock, product, wh in (await db.execute(stmt)).all():
        qty = float(stock.quantity or 0)
        minimum, reorder = effective_warehouse_thresholds(stock, product)
        status = compute_stock_status(qty, minimum, reorder)
        if status == "green":
            continue
        reorder_qty = float(stock.reorder_qty or 0)
        warehouse_rows.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": qty,
                "minimum_stock": minimum,
                "reorder_level": reorder,
                "stock_status": status,
                "reorder_qty": reorder_qty,
                "suggested_order_qty": max(reorder_qty, round(reorder - qty, 3)),
                "warehouse_id": wh.id,
                "warehouse_code": wh.code,
                "warehouse_name": wh.name,
                "store_id": wh.store_id,
                "scope": "warehouse",
            }
        )

    return {
        "count": len(product_rows),
        "products": product_rows,
        "warehouse_count": len(warehouse_rows),
        "warehouse_low_stock": warehouse_rows,
        "store_id": store_id,
        "warehouse_id": wh_filter,
        "store_name": store.name if store else None,
    }


async def inventory_expiry(
    db: AsyncSession,
    tenant_id: str,
    *,
    within_days: int = 30,
    company_id: str | None = None,
) -> dict:
    from app import catalog as catalog_svc

    batches = await catalog_svc.list_expiring_batches(
        db, tenant_id, within_days=within_days, company_id=company_id
    )
    return {
        "within_days": within_days,
        "count": len(batches),
        "batches": [catalog_svc.serialize_batch(b) for b in batches],
    }


async def purchases_summary(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    company_id: str | None = None,
) -> dict:
    stmt = select(m.PurchaseOrder).where(
        m.PurchaseOrder.tenant_id == tenant_id,
        m.PurchaseOrder.status != "cancelled",
    )
    if company_id:
        stmt = stmt.where(m.PurchaseOrder.company_id == company_id)
    if from_date:
        stmt = stmt.where(m.PurchaseOrder.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.PurchaseOrder.created_at <= to_date)
    orders = (await db.execute(stmt)).scalars().all()
    by_status: dict[str, int] = defaultdict(int)
    total = 0.0
    pending = 0.0
    for po in orders:
        by_status[po.status] += 1
        total += float(po.total_amount or 0)
        pending += max(float(po.total_amount or 0) - float(po.paid_amount or 0), 0)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "order_count": len(orders),
        "total_amount": round(total, 2),
        "outstanding_amount": round(pending, 2),
        "by_status": dict(by_status),
    }


async def purchases_by_supplier(
    db: AsyncSession,
    tenant_id: str,
    *,
    supplier_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    company_id: str | None = None,
) -> dict:
    stmt = select(m.PurchaseOrder, m.Party).join(m.Party, m.Party.id == m.PurchaseOrder.supplier_id).where(
        m.PurchaseOrder.tenant_id == tenant_id,
        m.PurchaseOrder.status != "cancelled",
    )
    stmt = apply_company_filter(stmt, m.PurchaseOrder.company_id, company_id)
    if supplier_id:
        stmt = stmt.where(m.PurchaseOrder.supplier_id == supplier_id)
    if from_date:
        stmt = stmt.where(m.PurchaseOrder.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.PurchaseOrder.created_at <= to_date)
    rows = (await db.execute(stmt)).all()
    agg: dict[str, dict] = {}
    for po, party in rows:
        row = agg.setdefault(
            party.id,
            {"supplier_id": party.id, "name": party.name, "order_count": 0, "total_amount": 0.0},
        )
        row["order_count"] += 1
        row["total_amount"] = round(row["total_amount"] + float(po.total_amount or 0), 2)
    suppliers = sorted(agg.values(), key=lambda x: x["total_amount"], reverse=True)
    return {"suppliers": suppliers, "total_amount": round(sum(s["total_amount"] for s in suppliers), 2)}


# Issued POs awaiting full receipt (BR-14.3 Pending Orders).
_PENDING_PO_STATUSES = frozenset({"sent", "partially_received"})


async def purchases_pending_orders(
    db: AsyncSession,
    tenant_id: str,
    *,
    supplier_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    company_id: str | None = None,
) -> dict:
    """POs not yet fully received — status sent or partially_received."""
    stmt = (
        select(m.PurchaseOrder, m.Party)
        .join(m.Party, m.Party.id == m.PurchaseOrder.supplier_id)
        .where(
            m.PurchaseOrder.tenant_id == tenant_id,
            m.PurchaseOrder.status.in_(_PENDING_PO_STATUSES),
        )
        .order_by(m.PurchaseOrder.created_at.asc())
    )
    stmt = apply_company_filter(stmt, m.PurchaseOrder.company_id, company_id)
    if supplier_id:
        stmt = stmt.where(m.PurchaseOrder.supplier_id == supplier_id)
    if from_date:
        stmt = stmt.where(m.PurchaseOrder.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.PurchaseOrder.created_at <= to_date)
    rows = (await db.execute(stmt)).all()
    orders: list[dict] = []
    total_amount = 0.0
    open_qty_total = 0.0
    for po, party in rows:
        items = (
            await db.execute(
                select(m.PurchaseOrderItem).where(
                    m.PurchaseOrderItem.tenant_id == tenant_id,
                    m.PurchaseOrderItem.purchase_order_id == po.id,
                )
            )
        ).scalars().all()
        ordered_qty = round(sum(float(i.quantity or 0) for i in items), 3)
        received_qty = round(sum(float(i.received_qty or 0) for i in items), 3)
        open_qty = round(max(ordered_qty - received_qty, 0.0), 3)
        amount = float(po.total_amount or 0)
        total_amount += amount
        open_qty_total += open_qty
        orders.append(
            {
                "id": po.id,
                "po_number": po.po_number,
                "supplier_id": party.id,
                "supplier_name": party.name,
                "status": po.status,
                "total_amount": round(amount, 2),
                "ordered_qty": ordered_qty,
                "received_qty": received_qty,
                "open_qty": open_qty,
                "due_date": po.due_date,
                "sent_at": po.sent_at,
                "created_at": po.created_at,
            }
        )
    return {
        "from_date": from_date,
        "to_date": to_date,
        "count": len(orders),
        "total_amount": round(total_amount, 2),
        "open_qty": round(open_qty_total, 3),
        "orders": orders,
    }


async def purchases_return_summary(
    db: AsyncSession,
    tenant_id: str,
    *,
    supplier_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    company_id: str | None = None,
) -> dict:
    """Purchase return summary by reason and supplier (BR-14.3)."""
    stmt = (
        select(m.PurchaseReturn, m.Party)
        .join(m.Party, m.Party.id == m.PurchaseReturn.supplier_id)
        .where(
            m.PurchaseReturn.tenant_id == tenant_id,
            m.PurchaseReturn.status != "cancelled",
        )
        .order_by(m.PurchaseReturn.created_at.desc())
    )
    stmt = apply_company_filter(stmt, m.PurchaseReturn.company_id, company_id)
    if supplier_id:
        stmt = stmt.where(m.PurchaseReturn.supplier_id == supplier_id)
    if from_date:
        stmt = stmt.where(
            func.coalesce(m.PurchaseReturn.posted_at, m.PurchaseReturn.created_at) >= from_date
        )
    if to_date:
        stmt = stmt.where(
            func.coalesce(m.PurchaseReturn.posted_at, m.PurchaseReturn.created_at) <= to_date
        )
    rows = (await db.execute(stmt)).all()

    by_reason: dict[str, dict] = {}
    by_supplier: dict[str, dict] = {}
    by_status: dict[str, int] = defaultdict(int)
    posted_total = 0.0
    posted_count = 0
    returns: list[dict] = []
    for ret, party in rows:
        by_status[ret.status] += 1
        amount = float(ret.total_amount or 0)
        reason = ret.reason or "other"
        reason_row = by_reason.setdefault(
            reason, {"reason": reason, "return_count": 0, "total_amount": 0.0}
        )
        reason_row["return_count"] += 1
        reason_row["total_amount"] = round(reason_row["total_amount"] + amount, 2)

        sup_row = by_supplier.setdefault(
            party.id,
            {
                "supplier_id": party.id,
                "name": party.name,
                "return_count": 0,
                "total_amount": 0.0,
            },
        )
        sup_row["return_count"] += 1
        sup_row["total_amount"] = round(sup_row["total_amount"] + amount, 2)

        if ret.status == "posted":
            posted_count += 1
            posted_total += amount

        returns.append(
            {
                "id": ret.id,
                "return_number": ret.return_number,
                "supplier_id": party.id,
                "supplier_name": party.name,
                "status": ret.status,
                "reason": reason,
                "total_amount": round(amount, 2),
                "debit_note_number": ret.debit_note_number,
                "posted_at": ret.posted_at,
                "created_at": ret.created_at,
            }
        )

    reasons = sorted(by_reason.values(), key=lambda x: x["total_amount"], reverse=True)
    suppliers = sorted(by_supplier.values(), key=lambda x: x["total_amount"], reverse=True)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "return_count": len(returns),
        "posted_count": posted_count,
        "total_amount": round(sum(float(r["total_amount"]) for r in returns), 2),
        "posted_amount": round(posted_total, 2),
        "by_status": dict(by_status),
        "by_reason": reasons,
        "by_supplier": suppliers,
        "returns": returns,
    }


async def expenses_summary(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    category_id: str | None = None,
    company_id: str | None = None,
) -> dict:
    stmt = select(m.Expense).where(
        m.Expense.tenant_id == tenant_id,
        m.Expense.status == "approved",
    )
    if company_id:
        stmt = stmt.where(m.Expense.company_id == company_id)
    if category_id:
        stmt = stmt.where(m.Expense.category_id == category_id)
    if from_date:
        stmt = stmt.where(m.Expense.expense_date >= from_date)
    if to_date:
        stmt = stmt.where(m.Expense.expense_date <= to_date)
    rows = (await db.execute(stmt)).scalars().all()
    by_category: dict[str, float] = defaultdict(float)
    for e in rows:
        by_category[e.category or "Uncategorized"] += float(e.amount or 0)
    categories = [
        {"category": k, "amount": round(v, 2)}
        for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    ]
    from app import expenses as expenses_svc

    budget = await expenses_svc.category_budget_variance(
        db, tenant_id, from_date=from_date, to_date=to_date
    )
    return {
        "count": len(rows),
        "total_amount": round(sum(float(e.amount or 0) for e in rows), 2),
        "by_category": categories,
        "budgets": budget,
    }


# IAS 7-style activity buckets for liquid GL movements (MVP heuristics).
_CASH_FLOW_FINANCING = frozenset({"opening_balance"})
_CASH_FLOW_TRANSFER = frozenset(
    {"liquid_deposit", "liquid_withdrawal", "liquid_transfer"}
)
_CASH_FLOW_INVESTING = frozenset()  # reserved; no dedicated fixed-asset sources yet


def classify_cash_flow_activity(source_type: str | None) -> str:
    """Map journal source_type → operating | investing | financing | transfer."""
    key = (source_type or "manual").strip().lower()
    if key in _CASH_FLOW_TRANSFER:
        return "transfer"
    if key in _CASH_FLOW_FINANCING:
        return "financing"
    if key in _CASH_FLOW_INVESTING:
        return "investing"
    return "operating"


def _empty_activity() -> dict:
    return {"inflows": 0.0, "outflows": 0.0, "net": 0.0, "lines": []}


async def cash_flow(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    branch_id: str | None = None,
) -> dict:
    """Cash flow from cash + bank GL accounts, split into O/I/F activities."""
    from app.accounting import ensure_default_accounts, resolve_journal_dimension_ids

    await ensure_default_accounts(db, tenant_id)
    resolved_store, resolved_branch, store_ids = await resolve_journal_dimension_ids(
        db, tenant_id=tenant_id, store_id=store_id, branch_id=branch_id
    )
    liquid = (
        await db.execute(
            select(m.Account).where(
                m.Account.tenant_id == tenant_id,
                (m.Account.is_cash_account.is_(True)) | (m.Account.is_bank_account.is_(True)),
            )
        )
    ).scalars().all()
    if not liquid:
        # Fallback for pre-flag DBs mid-migration
        cash = (
            await db.execute(
                select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == "1000")
            )
        ).scalar_one_or_none()
        liquid = [cash] if cash else []
    empty_sections = {
        "operating": _empty_activity(),
        "investing": _empty_activity(),
        "financing": _empty_activity(),
        "transfers": _empty_activity(),
    }
    if not liquid:
        return {
            "from_date": from_date.date().isoformat() if from_date else None,
            "to_date": to_date.date().isoformat() if to_date else None,
            "store_id": resolved_store,
            "branch_id": resolved_branch,
            "inflows": 0,
            "outflows": 0,
            "net": 0,
            "net_change": 0,
            "opening_cash": 0,
            "closing_cash": 0,
            "lines": [],
            "accounts": [],
            **empty_sections,
        }

    account_ids = [a.id for a in liquid]
    by_id = {a.id: a for a in liquid}

    # Opening cash = cumulative liquid deltas before from_date (posted only).
    opening_cash = 0.0
    if from_date:
        open_stmt = (
            select(m.JournalEntryLine, m.JournalEntry)
            .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
            .where(
                m.JournalEntryLine.tenant_id == tenant_id,
                m.JournalEntryLine.account_id.in_(account_ids),
                m.JournalEntry.status == "posted",
                m.JournalEntry.entry_date < from_date,
            )
        )
        if store_ids is not None:
            if store_ids:
                open_stmt = open_stmt.where(m.JournalEntry.store_id.in_(store_ids))
            else:
                open_stmt = open_stmt.where(m.JournalEntry.store_id.in_([]))
        for line, _entry in (await db.execute(open_stmt)).all():
            opening_cash += float(line.debit or 0) - float(line.credit or 0)

    stmt = (
        select(m.JournalEntryLine, m.JournalEntry)
        .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntryLine.account_id.in_(account_ids),
            m.JournalEntry.status == "posted",
        )
    )
    if from_date:
        stmt = stmt.where(m.JournalEntry.entry_date >= from_date)
    if to_date:
        stmt = stmt.where(m.JournalEntry.entry_date <= to_date)
    if store_ids is not None:
        if store_ids:
            stmt = stmt.where(m.JournalEntry.store_id.in_(store_ids))
        else:
            stmt = stmt.where(m.JournalEntry.store_id.in_([]))
    rows = (await db.execute(stmt.order_by(m.JournalEntry.entry_date.asc()))).all()

    sections = {
        "operating": _empty_activity(),
        "investing": _empty_activity(),
        "financing": _empty_activity(),
        "transfers": _empty_activity(),
    }
    inflows = 0.0
    outflows = 0.0
    lines = []
    for line, entry in rows:
        debit = float(line.debit or 0)
        credit = float(line.credit or 0)
        inflows += debit
        outflows += credit
        activity = classify_cash_flow_activity(entry.source_type)
        section_key = "transfers" if activity == "transfer" else activity
        section = sections[section_key]
        section["inflows"] = round(section["inflows"] + debit, 2)
        section["outflows"] = round(section["outflows"] + credit, 2)
        section["net"] = round(section["inflows"] - section["outflows"], 2)
        acct = by_id.get(line.account_id)
        row = {
            "date": entry.entry_date,
            "entry_number": entry.entry_number,
            "description": entry.description,
            "account_code": acct.code if acct else None,
            "account_name": acct.name if acct else None,
            "inflow": debit,
            "outflow": credit,
            "source_type": entry.source_type,
            "activity": activity,
        }
        section["lines"].append(row)
        lines.append(row)

    period_net = round(inflows - outflows, 2)
    # Statement net change excludes pure cash↔bank transfers (cash equivalents).
    net_change = round(
        sections["operating"]["net"]
        + sections["investing"]["net"]
        + sections["financing"]["net"],
        2,
    )
    closing_cash = round(opening_cash + period_net, 2)

    return {
        "from_date": from_date.date().isoformat() if from_date else None,
        "to_date": to_date.date().isoformat() if to_date else None,
        "store_id": resolved_store,
        "branch_id": resolved_branch,
        "inflows": round(inflows, 2),
        "outflows": round(outflows, 2),
        "net": period_net,
        "net_change": net_change,
        "opening_cash": round(opening_cash, 2),
        "closing_cash": closing_cash,
        "operating": sections["operating"],
        "investing": sections["investing"],
        "financing": sections["financing"],
        "transfers": sections["transfers"],
        "lines": lines,
        "accounts": [{"id": a.id, "code": a.code, "name": a.name} for a in liquid],
    }


async def balance_sheet(
    db: AsyncSession,
    tenant_id: str,
    *,
    as_of: datetime | None = None,
    store_id: str | None = None,
    branch_id: str | None = None,
) -> dict:
    """Point-in-time balance sheet; optional as_of / store / branch from posted journals."""
    from app.accounting import account_balances_through, resolve_journal_dimension_ids

    resolved_store, resolved_branch, store_ids = await resolve_journal_dimension_ids(
        db, tenant_id=tenant_id, store_id=store_id, branch_id=branch_id
    )
    accounts, bal_by_id = await account_balances_through(
        db, tenant_id, as_of=as_of, store_ids=store_ids
    )

    def rows_for(account_type: str) -> list[dict]:
        return [
            {
                "code": a.code,
                "name": a.name,
                "balance": round(float(bal_by_id.get(a.id, 0.0)), 2),
            }
            for a in accounts
            if a.account_type == account_type
        ]

    assets = rows_for("asset")
    liabilities = rows_for("liability")
    equity = rows_for("equity")
    # Retained earnings proxy from income - expense (not posted to equity yet)
    income = sum(
        float(bal_by_id.get(a.id, 0.0)) for a in accounts if a.account_type == "income"
    )
    expense = sum(
        float(bal_by_id.get(a.id, 0.0)) for a in accounts if a.account_type == "expense"
    )
    retained = round(income - expense, 2)
    if abs(retained) > 0.0001:
        equity = [
            *equity,
            {"code": "RE", "name": "Retained earnings (computed)", "balance": retained},
        ]

    total_assets = round(sum(r["balance"] for r in assets), 2)
    total_liabilities = round(sum(r["balance"] for r in liabilities), 2)
    total_equity = round(sum(r["balance"] for r in equity), 2)
    return {
        "as_of": (as_of or datetime.utcnow()).date().isoformat(),
        "store_id": resolved_store,
        "branch_id": resolved_branch,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_liabilities_and_equity": round(total_liabilities + total_equity, 2),
        "balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.01,
    }
