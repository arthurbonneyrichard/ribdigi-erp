"""Operational and financial report aggregations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m


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


async def _resolve_sales_store(
    db: AsyncSession, tenant_id: str, store_id: str | None
) -> tuple[str | None, str | None]:
    """Validate optional store filter; returns (store_id, store_name)."""
    if not store_id:
        return None, None
    store = (
        await db.execute(
            select(m.Store).where(
                m.Store.tenant_id == tenant_id,
                m.Store.id == store_id,
            )
        )
    ).scalar_one_or_none()
    if not store:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Store not found")
    return store.id, store.name


async def sales_daily(
    db: AsyncSession,
    tenant_id: str,
    date: datetime | None = None,
    *,
    store_id: str | None = None,
) -> dict:
    day = date or datetime.utcnow()
    start, end = day_bounds(day)
    store_id, store_name = await _resolve_sales_store(db, tenant_id, store_id)

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "sent", "partial", "paid", "overdue"]),
        m.SalesInvoice.posted_at >= start,
        m.SalesInvoice.posted_at <= end,
    )
    if store_id:
        inv_stmt = inv_stmt.where(m.SalesInvoice.store_id == store_id)
    invoices = (await db.execute(inv_stmt)).scalars().all()

    pos_stmt = (
        select(m.Transaction, m.PosSession)
        .outerjoin(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
            m.Transaction.created_at >= start,
            m.Transaction.created_at <= end,
        )
    )
    if store_id:
        pos_stmt = pos_stmt.where(m.PosSession.store_id == store_id)
    pos_rows = (await db.execute(pos_stmt)).all()

    invoice_total = sum(float(i.total_amount or 0) for i in invoices)
    invoice_tax = sum(float(i.tax_amount or 0) for i in invoices)
    invoice_discount = sum(float(i.discount_amount or 0) for i in invoices)
    pos_total = sum(float(t.total or 0) for t, _ in pos_rows)
    pos_tax = sum(float(t.tax or 0) for t, _ in pos_rows)

    return {
        "date": start.date().isoformat(),
        "store_id": store_id,
        "store_name": store_name,
        "invoice_count": len(invoices),
        "pos_count": len(pos_rows),
        "invoice_revenue": round(invoice_total, 2),
        "pos_revenue": round(pos_total, 2),
        "total_revenue": round(invoice_total + pos_total, 2),
        "tax": round(invoice_tax + pos_tax, 2),
        "discounts": round(invoice_discount, 2),
        "net_sales": round(invoice_total + pos_total - invoice_discount, 2),
    }


async def sales_monthly(
    db: AsyncSession,
    tenant_id: str,
    year: int,
    month: int,
    *,
    store_id: str | None = None,
) -> dict:
    start, end = month_bounds(year, month)
    store_id, store_name = await _resolve_sales_store(db, tenant_id, store_id)

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "sent", "partial", "paid", "overdue"]),
        m.SalesInvoice.posted_at >= start,
        m.SalesInvoice.posted_at <= end,
    )
    if store_id:
        inv_stmt = inv_stmt.where(m.SalesInvoice.store_id == store_id)
    invoices = (await db.execute(inv_stmt)).scalars().all()

    pos_stmt = (
        select(m.Transaction, m.PosSession)
        .outerjoin(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
            m.Transaction.created_at >= start,
            m.Transaction.created_at <= end,
        )
    )
    if store_id:
        pos_stmt = pos_stmt.where(m.PosSession.store_id == store_id)
    pos_rows = (await db.execute(pos_stmt)).all()

    by_day: dict[str, float] = defaultdict(float)
    for inv in invoices:
        key = (inv.posted_at or inv.created_at).date().isoformat()
        by_day[key] += float(inv.total_amount or 0)
    for tx, _ in pos_rows:
        key = tx.created_at.date().isoformat()
        by_day[key] += float(tx.total or 0)

    total = sum(by_day.values())
    prev_year, prev_month = (year - 1, month) if month == 1 else (year, month - 1)
    prev = await sales_monthly_total(
        db, tenant_id, prev_year, prev_month, store_id=store_id
    )
    return {
        "year": year,
        "month": month,
        "store_id": store_id,
        "store_name": store_name,
        "invoice_count": len(invoices),
        "pos_count": len(pos_rows),
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
    store_id: str | None = None,
) -> float:
    start, end = month_bounds(year, month)
    inv_stmt = select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "sent", "partial", "paid", "overdue"]),
        m.SalesInvoice.posted_at >= start,
        m.SalesInvoice.posted_at <= end,
    )
    if store_id:
        inv_stmt = inv_stmt.where(m.SalesInvoice.store_id == store_id)
    inv = float((await db.execute(inv_stmt)).scalar() or 0)

    pos_stmt = (
        select(func.coalesce(func.sum(m.Transaction.total), 0))
        .select_from(m.Transaction)
        .outerjoin(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
            m.Transaction.created_at >= start,
            m.Transaction.created_at <= end,
        )
    )
    if store_id:
        pos_stmt = pos_stmt.where(m.PosSession.store_id == store_id)
    pos = float((await db.execute(pos_stmt)).scalar() or 0)
    return round(inv + pos, 2)


async def sales_by_product(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    category_id: str | None = None,
) -> dict:
    """Product-wise quantity and revenue; optional store / category filters (BR-14.1)."""
    category_name: str | None = None
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
        category_name = cat.name

    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.id == store_id,
                    m.Store.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not store:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Store not found")

    stmt = (
        select(m.SalesInvoiceItem, m.SalesInvoice, m.Product)
        .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
        .join(m.Product, m.Product.id == m.SalesInvoiceItem.product_id)
        .where(
            m.SalesInvoiceItem.tenant_id == tenant_id,
            m.SalesInvoice.status.in_(["posted", "sent", "partial", "paid", "overdue"]),
        )
    )
    if from_date:
        stmt = stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        stmt = stmt.where(m.SalesInvoice.posted_at <= to_date)
    if store_id:
        stmt = stmt.where(m.SalesInvoice.store_id == store_id)
    if category_id:
        stmt = stmt.where(m.Product.category_id == category_id)
    rows = (await db.execute(stmt)).all()

    cat_ids = {p.category_id for _, _, p in rows if p.category_id}
    # Include POS payload items where possible
    pos_stmt = select(m.Transaction).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
    )
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    if store_id:
        pos_stmt = (
            pos_stmt.join(m.PosSession, m.PosSession.id == m.Transaction.session_id).where(
                m.PosSession.tenant_id == tenant_id,
                m.PosSession.store_id == store_id,
            )
        )
    pos_txs = (await db.execute(pos_stmt)).scalars().all()

    product_cache: dict[str, m.Product] = {}
    for tx in pos_txs:
        for line in (tx.payload or {}).get("items") or []:
            pid = line.get("product_id")
            if not pid or pid in product_cache:
                continue
            product = await db.get(m.Product, pid)
            if product and product.tenant_id == tenant_id:
                product_cache[pid] = product
                if product.category_id:
                    cat_ids.add(product.category_id)

    cat_names: dict[str, str] = {}
    if cat_ids:
        for c in (
            await db.execute(
                select(m.ProductCategory).where(
                    m.ProductCategory.tenant_id == tenant_id,
                    m.ProductCategory.id.in_(list(cat_ids)),
                )
            )
        ).scalars().all():
            cat_names[c.id] = c.name

    def _bucket(agg: dict[str, dict], product: m.Product) -> dict:
        return agg.setdefault(
            product.id,
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "category_id": product.category_id,
                "category_name": cat_names.get(product.category_id or "", None),
                "quantity": 0.0,
                "revenue": 0.0,
            },
        )

    agg: dict[str, dict] = {}
    for item, _inv, product in rows:
        row = _bucket(agg, product)
        row["quantity"] = round(row["quantity"] + float(item.quantity or 0), 3)
        row["revenue"] = round(row["revenue"] + float(item.line_total or 0), 2)

    for tx in pos_txs:
        for line in (tx.payload or {}).get("items") or []:
            pid = line.get("product_id")
            if not pid:
                continue
            product = product_cache.get(pid)
            if not product:
                continue
            if category_id and product.category_id != category_id:
                continue
            row = _bucket(agg, product)
            qty = float(line.get("quantity") or 0)
            revenue = float(
                line.get("line_total")
                or (float(line.get("unit_price") or product.selling_price or 0) * qty)
            )
            row["quantity"] = round(row["quantity"] + qty, 3)
            row["revenue"] = round(row["revenue"] + revenue, 2)

    products = sorted(agg.values(), key=lambda x: x["revenue"], reverse=True)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "store_id": store_id,
        "category_id": category_id,
        "category_name": category_name,
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
    store_id: str | None = None,
    limit: int | None = None,
) -> dict:
    """Aggregate posted invoices + POS sales by customer (BR-14.1).

    Ranked by revenue (top customers). Frequency = sale_count.
    Walk-in / missing party buckets as ``customer_id=null`` / name Walk-in.
    Optional ``store_id`` scopes invoices by ``SalesInvoice.store_id`` and POS by session store.
    """

    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.id == store_id,
                    m.Store.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not store:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Store not found")

    def _bucket(agg: dict[str, dict], customer_id: str | None) -> dict:
        key = customer_id or "walk_in"
        return agg.setdefault(
            key,
            {
                "customer_id": None if key == "walk_in" else key,
                "name": "Walk-in",
                "email": None,
                "phone": None,
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
        m.SalesInvoice.status.in_(["posted", "sent", "partial", "paid", "overdue"]),
    )
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    if store_id:
        inv_stmt = inv_stmt.where(m.SalesInvoice.store_id == store_id)
    for inv in (await db.execute(inv_stmt)).scalars().all():
        row = _bucket(agg, inv.customer_id)
        total = float(inv.total_amount or 0)
        tax = float(inv.tax_amount or 0)
        row["invoice_count"] += 1
        row["invoice_revenue"] = round(row["invoice_revenue"] + total, 2)
        row["invoice_tax"] = round(row["invoice_tax"] + tax, 2)
        row["sale_count"] += 1
        row["revenue"] = round(row["revenue"] + total, 2)
        row["tax"] = round(row["tax"] + tax, 2)

    pos_stmt = select(m.Transaction).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
    )
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    if store_id:
        pos_stmt = pos_stmt.join(m.PosSession, m.PosSession.id == m.Transaction.session_id).where(
            m.PosSession.tenant_id == tenant_id,
            m.PosSession.store_id == store_id,
        )
    for tx in (await db.execute(pos_stmt)).scalars().all():
        row = _bucket(agg, tx.party_id)
        total = float(tx.total or 0)
        tax = float(tx.tax or 0)
        row["pos_count"] += 1
        row["pos_revenue"] = round(row["pos_revenue"] + total, 2)
        row["pos_tax"] = round(row["pos_tax"] + tax, 2)
        row["sale_count"] += 1
        row["revenue"] = round(row["revenue"] + total, 2)
        row["tax"] = round(row["tax"] + tax, 2)

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
        for key, row in agg.items():
            if key == "walk_in":
                continue
            party = by_id.get(key)
            if party:
                row["name"] = party.name
                row["email"] = party.email
                row["phone"] = party.phone

    for row in agg.values():
        row["avg_ticket"] = (
            round(row["revenue"] / row["sale_count"], 2) if row["sale_count"] else 0.0
        )

    customers = sorted(agg.values(), key=lambda x: x["revenue"], reverse=True)
    if limit is not None and limit > 0:
        customers = customers[:limit]
    return {
        "from_date": from_date,
        "to_date": to_date,
        "store_id": store_id,
        "customers": customers,
        "total_revenue": round(sum(c["revenue"] for c in customers), 2),
        "total_sales": sum(c["sale_count"] for c in customers),
        "invoice_revenue": round(sum(c["invoice_revenue"] for c in customers), 2),
        "pos_revenue": round(sum(c["pos_revenue"] for c in customers), 2),
        "customer_count": len(customers),
    }


async def sales_returns_summary(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    customer_id: str | None = None,
    reason: str | None = None,
    status: str | None = None,
    store_id: str | None = None,
) -> dict:
    """Sales return summary by period / reason / customer (BR-14.1).

    Optional ``store_id`` scopes returns to the original invoice store.
    """
    from app.sales_docs import RETURN_REASONS

    store_id, store_name = await _resolve_sales_store(db, tenant_id, store_id)

    if reason:
        key = reason.strip().lower()
        if key not in RETURN_REASONS:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail=f"reason must be one of {sorted(RETURN_REASONS)}",
            )
        reason = key
    if status:
        status = status.strip().lower()
        if status not in {"draft", "posted", "cancelled"}:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail="status must be draft, posted, or cancelled",
            )

    stmt = (
        select(m.SalesReturn, m.Party)
        .join(m.Party, m.Party.id == m.SalesReturn.customer_id)
        .where(m.SalesReturn.tenant_id == tenant_id)
        .order_by(m.SalesReturn.created_at.desc())
    )
    if store_id:
        stmt = stmt.join(
            m.SalesInvoice, m.SalesInvoice.id == m.SalesReturn.sales_invoice_id
        ).where(m.SalesInvoice.store_id == store_id)
    if customer_id:
        stmt = stmt.where(m.SalesReturn.customer_id == customer_id)
    if reason:
        stmt = stmt.where(m.SalesReturn.reason == reason)
    if status:
        stmt = stmt.where(m.SalesReturn.status == status)
    if from_date:
        stmt = stmt.where(m.SalesReturn.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.SalesReturn.created_at <= to_date)

    rows = (await db.execute(stmt)).all()
    by_reason: dict[str, dict] = {}
    by_status: dict[str, int] = defaultdict(int)
    by_customer: dict[str, dict] = {}
    returns: list[dict] = []
    total_amount = 0.0
    posted_amount = 0.0
    total_qty = 0.0
    refunded_total = 0.0

    for ret, party in rows:
        items = (
            await db.execute(
                select(m.SalesReturnItem).where(
                    m.SalesReturnItem.tenant_id == tenant_id,
                    m.SalesReturnItem.sales_return_id == ret.id,
                )
            )
        ).scalars().all()
        qty = round(sum(float(i.quantity or 0) for i in items), 3)
        amount = float(ret.total_amount or 0)
        refunded = float(ret.refunded_amount or 0)
        total_amount += amount
        total_qty += qty
        refunded_total += refunded
        by_status[ret.status] += 1
        if ret.status == "posted":
            posted_amount += amount

        reason_row = by_reason.setdefault(
            ret.reason or "other",
            {"reason": ret.reason or "other", "return_count": 0, "total_amount": 0.0, "quantity": 0.0},
        )
        reason_row["return_count"] += 1
        reason_row["total_amount"] = round(reason_row["total_amount"] + amount, 2)
        reason_row["quantity"] = round(reason_row["quantity"] + qty, 3)

        cust = by_customer.setdefault(
            party.id,
            {
                "customer_id": party.id,
                "name": party.name,
                "return_count": 0,
                "total_amount": 0.0,
                "quantity": 0.0,
            },
        )
        cust["return_count"] += 1
        cust["total_amount"] = round(cust["total_amount"] + amount, 2)
        cust["quantity"] = round(cust["quantity"] + qty, 3)

        returns.append(
            {
                "id": ret.id,
                "return_number": ret.return_number,
                "credit_note_number": ret.credit_note_number,
                "customer_id": party.id,
                "customer_name": party.name,
                "status": ret.status,
                "reason": ret.reason,
                "restock": bool(ret.restock),
                "settlement_method": ret.settlement_method,
                "quantity": qty,
                "subtotal": float(ret.subtotal or 0),
                "tax_amount": float(ret.tax_amount or 0),
                "total_amount": amount,
                "refunded_amount": refunded,
                "sales_invoice_id": ret.sales_invoice_id,
                "posted_at": ret.posted_at,
                "created_at": ret.created_at,
            }
        )

    reasons = sorted(by_reason.values(), key=lambda x: x["total_amount"], reverse=True)
    customers = sorted(by_customer.values(), key=lambda x: x["total_amount"], reverse=True)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "customer_id": customer_id,
        "reason": reason,
        "status": status,
        "store_id": store_id,
        "store_name": store_name,
        "return_count": len(returns),
        "total_amount": round(total_amount, 2),
        "posted_amount": round(posted_amount, 2),
        "total_quantity": round(total_qty, 3),
        "refunded_amount": round(refunded_total, 2),
        "by_status": dict(by_status),
        "by_reason": reasons,
        "by_customer": customers,
        "returns": returns,
    }


async def _resolve_department_filter(
    db: AsyncSession, tenant_id: str, department_id: str | None
) -> tuple[str | None, str | None, set[str] | None]:
    """Validate department and return (id, name, user_ids). user_ids is None when unfiltered."""
    if not department_id:
        return None, None, None
    from fastapi import HTTPException

    dept = (
        await db.execute(
            select(m.Department).where(
                m.Department.tenant_id == tenant_id,
                m.Department.id == department_id,
            )
        )
    ).scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    user_ids = set(
        (
            await db.execute(
                select(m.User.id).where(
                    m.User.tenant_id == tenant_id,
                    m.User.department_id == department_id,
                )
            )
        )
        .scalars()
        .all()
    )
    return dept.id, dept.name, user_ids


async def sales_by_salesperson(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    department_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    """Aggregate posted invoices + POS sales by salesperson (invoice created_by / POS session user).

    Optional ``store_id`` scopes invoices by ``SalesInvoice.store_id`` and POS by session store.
    """
    dept_id, dept_name, dept_user_ids = await _resolve_department_filter(
        db, tenant_id, department_id
    )
    store_name = None
    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.tenant_id == tenant_id,
                    m.Store.id == store_id,
                )
            )
        ).scalar_one_or_none()
        if not store:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Store not found")
        store_id = store.id
        store_name = store.name

    def _bucket(agg: dict[str, dict], user_id: str | None) -> dict:
        key = user_id or "unknown"
        return agg.setdefault(
            key,
            {
                "user_id": None if key == "unknown" else key,
                "full_name": "Unknown",
                "email": None,
                "role": None,
                "department_id": None,
                "department_name": None,
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
        m.SalesInvoice.status.in_(["posted", "sent", "partial", "paid", "overdue"]),
    )
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    if store_id:
        inv_stmt = inv_stmt.where(m.SalesInvoice.store_id == store_id)
    if dept_user_ids is not None:
        if not dept_user_ids:
            inv_stmt = inv_stmt.where(m.SalesInvoice.id == None)  # noqa: E711 — empty dept membership
        else:
            inv_stmt = inv_stmt.where(m.SalesInvoice.created_by.in_(dept_user_ids))
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
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    if store_id:
        pos_stmt = pos_stmt.where(m.PosSession.store_id == store_id)
    if dept_user_ids is not None:
        if not dept_user_ids:
            pos_stmt = pos_stmt.where(m.Transaction.id == None)  # noqa: E711
        else:
            pos_stmt = pos_stmt.where(m.PosSession.user_id.in_(dept_user_ids))
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
    dept_names: dict[str, str] = {}
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
        need_depts = {u.department_id for u in users if u.department_id}
        if need_depts:
            depts = (
                await db.execute(
                    select(m.Department).where(
                        m.Department.tenant_id == tenant_id,
                        m.Department.id.in_(need_depts),
                    )
                )
            ).scalars().all()
            dept_names = {d.id: d.name for d in depts}
        for key, row in agg.items():
            if key == "unknown":
                continue
            user = by_id.get(key)
            if user:
                row["full_name"] = user.full_name
                row["email"] = user.email
                row["role"] = user.role
                row["department_id"] = user.department_id
                row["department_name"] = dept_names.get(user.department_id or "", None)

    for row in agg.values():
        row["avg_ticket"] = round(row["revenue"] / row["sale_count"], 2) if row["sale_count"] else 0.0

    salespeople = sorted(agg.values(), key=lambda x: x["revenue"], reverse=True)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "department_id": dept_id,
        "department_name": dept_name,
        "store_id": store_id,
        "store_name": store_name,
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
    department_id: str | None = None,
) -> dict:
    """Aggregate posted invoices + POS sales by store (invoice.store_id / POS session.store_id)."""
    dept_id, dept_name, dept_user_ids = await _resolve_department_filter(
        db, tenant_id, department_id
    )

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
    stores = (
        await db.execute(
            select(m.Store).where(m.Store.tenant_id == tenant_id).order_by(m.Store.name)
        )
    ).scalars().all()
    for store in stores:
        row = _bucket(agg, store.id)
        row["name"] = store.name
        row["code"] = store.code

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "sent", "partial", "paid", "overdue"]),
    )
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    if dept_user_ids is not None:
        if not dept_user_ids:
            inv_stmt = inv_stmt.where(m.SalesInvoice.id == None)  # noqa: E711 — empty dept membership
        else:
            inv_stmt = inv_stmt.where(m.SalesInvoice.created_by.in_(dept_user_ids))
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
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    if dept_user_ids is not None:
        if not dept_user_ids:
            pos_stmt = pos_stmt.where(m.Transaction.id == None)  # noqa: E711
        else:
            pos_stmt = pos_stmt.where(m.PosSession.user_id.in_(dept_user_ids))
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
        if dept_user_ids is not None and row["sale_count"] == 0:
            continue
        stores_out.append(row)
    stores_out.sort(key=lambda x: x["revenue"], reverse=True)

    return {
        "from_date": from_date,
        "to_date": to_date,
        "department_id": dept_id,
        "department_name": dept_name,
        "stores": stores_out,
        "total_revenue": round(sum(s["revenue"] for s in stores_out), 2),
        "total_sales": sum(s["sale_count"] for s in stores_out),
        "invoice_revenue": round(sum(s["invoice_revenue"] for s in stores_out), 2),
        "pos_revenue": round(sum(s["pos_revenue"] for s in stores_out), 2),
    }


async def sales_by_department(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    department_id: str | None = None,
) -> dict:
    """Aggregate posted invoices + POS sales by seller department (BR-2.5)."""
    filter_id, filter_name, _ = await _resolve_department_filter(db, tenant_id, department_id)

    def _bucket(agg: dict[str, dict], dept_key: str | None) -> dict:
        key = dept_key or "unknown"
        return agg.setdefault(
            key,
            {
                "department_id": None if key == "unknown" else key,
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
    depts = (
        await db.execute(
            select(m.Department)
            .where(m.Department.tenant_id == tenant_id)
            .order_by(m.Department.name)
        )
    ).scalars().all()
    for dept in depts:
        if filter_id and dept.id != filter_id:
            continue
        row = _bucket(agg, dept.id)
        row["name"] = dept.name
        row["code"] = dept.code

    users = (
        await db.execute(select(m.User).where(m.User.tenant_id == tenant_id))
    ).scalars().all()
    user_dept = {u.id: u.department_id for u in users}

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "sent", "partial", "paid", "overdue"]),
    )
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    for inv in (await db.execute(inv_stmt)).scalars().all():
        seller_dept = user_dept.get(inv.created_by) if inv.created_by else None
        if filter_id and seller_dept != filter_id:
            continue
        row = _bucket(agg, seller_dept)
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
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    for tx, session in (await db.execute(pos_stmt)).all():
        user_id = session.user_id if session else None
        seller_dept = user_dept.get(user_id) if user_id else None
        if filter_id and seller_dept != filter_id:
            continue
        row = _bucket(agg, seller_dept)
        total = float(tx.total or 0)
        tax = float(tx.tax or 0)
        row["pos_count"] += 1
        row["pos_revenue"] = round(row["pos_revenue"] + total, 2)
        row["pos_tax"] = round(row["pos_tax"] + tax, 2)
        row["sale_count"] += 1
        row["revenue"] = round(row["revenue"] + total, 2)
        row["tax"] = round(row["tax"] + tax, 2)

    orphan_ids = [k for k in agg.keys() if k != "unknown" and agg[k]["code"] is None]
    if orphan_ids:
        found = (
            await db.execute(
                select(m.Department).where(
                    m.Department.tenant_id == tenant_id,
                    m.Department.id.in_(orphan_ids),
                )
            )
        ).scalars().all()
        by_id = {d.id: d for d in found}
        for key in orphan_ids:
            dept = by_id.get(key)
            if dept:
                agg[key]["name"] = dept.name
                agg[key]["code"] = dept.code
            else:
                agg[key]["name"] = f"Department {key[:8]}"

    for row in agg.values():
        row["avg_ticket"] = round(row["revenue"] / row["sale_count"], 2) if row["sale_count"] else 0.0

    departments_out = []
    for key, row in agg.items():
        if key == "unknown" and row["sale_count"] == 0:
            continue
        if filter_id and key != filter_id and row["sale_count"] == 0:
            continue
        departments_out.append(row)
    departments_out.sort(key=lambda x: x["revenue"], reverse=True)

    return {
        "from_date": from_date,
        "to_date": to_date,
        "department_id": filter_id,
        "department_name": filter_name,
        "departments": departments_out,
        "total_revenue": round(sum(s["revenue"] for s in departments_out), 2),
        "total_sales": sum(s["sale_count"] for s in departments_out),
        "invoice_revenue": round(sum(s["invoice_revenue"] for s in departments_out), 2),
        "pos_revenue": round(sum(s["pos_revenue"] for s in departments_out), 2),
    }


async def inventory_balance(
    db: AsyncSession,
    tenant_id: str,
    warehouse_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    """Current stock per product (BR-14.2).

    Optional ``warehouse_id`` / ``store_id`` scopes to warehouse stock rows
    (store expands to linked warehouses). Unfiltered uses company ``product.stock_qty``.
    """
    (
        warehouse_id,
        warehouse_name,
        store_id,
        store_name,
        warehouse_ids,
    ) = await _resolve_purchase_location_filters(
        db, tenant_id, warehouse_id=warehouse_id, store_id=store_id
    )

    if warehouse_ids is not None:
        if not warehouse_ids:
            items: list[dict] = []
        else:
            rows = (
                await db.execute(
                    select(m.WarehouseStock, m.Product)
                    .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
                    .where(
                        m.WarehouseStock.tenant_id == tenant_id,
                        m.WarehouseStock.warehouse_id.in_(warehouse_ids),
                    )
                    .order_by(m.Product.name)
                )
            ).all()
            agg: dict[str, dict] = {}
            for stock, product in rows:
                row = agg.get(product.id)
                qty = float(stock.quantity or 0)
                if not row:
                    agg[product.id] = {
                        "product_id": product.id,
                        "sku": product.sku,
                        "name": product.name,
                        "warehouse_id": warehouse_id
                        if warehouse_id
                        else (stock.warehouse_id if len(warehouse_ids) == 1 else None),
                        "quantity": qty,
                        "cost_price": float(product.cost_price or 0),
                        "value": 0.0,
                    }
                else:
                    row["quantity"] = round(float(row["quantity"]) + qty, 3)
            items = []
            for row in agg.values():
                row["value"] = round(
                    float(row["quantity"]) * float(row["cost_price"] or 0), 2
                )
                items.append(row)
            items.sort(key=lambda x: x["name"] or "")
    else:
        products = (
            await db.execute(
                select(m.Product)
                .where(m.Product.tenant_id == tenant_id, m.Product.is_active == True)  # noqa: E712
                .order_by(m.Product.name)
            )
        ).scalars().all()
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
        "warehouse_name": warehouse_name,
        "store_id": store_id,
        "store_name": store_name,
        "items": items,
        "total_quantity": round(sum(i["quantity"] for i in items), 3),
        "total_value": round(sum(i["value"] for i in items), 2),
    }


SUPPORTED_VALUATION_METHODS = frozenset({"standard"})


async def inventory_valuation(
    db: AsyncSession,
    tenant_id: str,
    *,
    method: str | None = "standard",
    warehouse_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    """Stock valuation at standard (product) cost — BR-14.2 / BR-5.4.

    FIFO / LIFO / weighted average are deferred; requesting them returns 400.
    """
    from fastapi import HTTPException

    method_key = (method or "standard").strip().lower() or "standard"
    if method_key not in SUPPORTED_VALUATION_METHODS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Costing method '{method_key}' is not supported. "
                "Use method=standard (FIFO/LIFO/weighted average deferred)."
            ),
        )

    balance = await inventory_balance(
        db, tenant_id, warehouse_id=warehouse_id, store_id=store_id
    )
    items = [
        {
            "product_id": i["product_id"],
            "sku": i["sku"],
            "name": i["name"],
            "warehouse_id": i.get("warehouse_id"),
            "quantity": i["quantity"],
            "unit_cost": i["cost_price"],
            "cost_price": i["cost_price"],  # back-compat alias
            "value": i["value"],
        }
        for i in balance["items"]
        if abs(float(i["quantity"] or 0)) > 0.0001 or abs(float(i["value"] or 0)) > 0.0001
    ]
    return {
        "method": method_key,
        "warehouse_id": balance.get("warehouse_id"),
        "warehouse_name": balance.get("warehouse_name"),
        "store_id": balance.get("store_id"),
        "store_name": balance.get("store_name"),
        "items": items,
        "total_quantity": round(sum(float(i["quantity"]) for i in items), 3),
        "total_value": round(sum(float(i["value"]) for i in items), 2),
    }


async def inventory_movements(
    db: AsyncSession,
    tenant_id: str,
    *,
    product_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    warehouse_id: str | None = None,
    store_id: str | None = None,
    movement_type: str | None = None,
    created_by: str | None = None,
    reason: str | None = None,
    limit: int = 200,
) -> dict:
    """Stock movement history (BR-14.2 / BR-5.3).

    Optional ``warehouse_id`` / ``store_id`` (via warehouse store link),
    ``movement_type``, ``created_by``, and ``reason`` filters. Each row includes
    product sku/name and acting user attribution (immutable audit trail).
    """
    (
        warehouse_id,
        warehouse_name,
        store_id,
        store_name,
        warehouse_ids,
    ) = await _resolve_purchase_location_filters(
        db, tenant_id, warehouse_id=warehouse_id, store_id=store_id
    )
    if movement_type:
        movement_type = movement_type.strip().lower()
    if created_by:
        created_by = created_by.strip() or None
    if reason:
        reason = reason.strip().lower() or None

    stmt = select(m.StockMovement).where(m.StockMovement.tenant_id == tenant_id)
    if product_id:
        stmt = stmt.where(m.StockMovement.product_id == product_id)
    if from_date:
        stmt = stmt.where(m.StockMovement.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.StockMovement.created_at <= to_date)
    if movement_type:
        stmt = stmt.where(m.StockMovement.movement_type == movement_type)
    if created_by:
        stmt = stmt.where(m.StockMovement.created_by == created_by)
    if reason:
        stmt = stmt.where(m.StockMovement.reason == reason)
    if warehouse_ids is not None:
        if not warehouse_ids:
            stmt = stmt.where(m.StockMovement.id == None)  # noqa: E711
        else:
            stmt = stmt.where(m.StockMovement.warehouse_id.in_(warehouse_ids))
    stmt = stmt.order_by(m.StockMovement.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()

    product_ids = {r.product_id for r in rows if r.product_id}
    user_ids = {r.created_by for r in rows if r.created_by}
    products_by_id: dict[str, m.Product] = {}
    users_by_id: dict[str, m.User] = {}
    if product_ids:
        products_by_id = {
            p.id: p
            for p in (
                await db.execute(
                    select(m.Product).where(
                        m.Product.tenant_id == tenant_id,
                        m.Product.id.in_(product_ids),
                    )
                )
            ).scalars().all()
        }
    if user_ids:
        users_by_id = {
            u.id: u
            for u in (
                await db.execute(
                    select(m.User).where(
                        m.User.tenant_id == tenant_id,
                        m.User.id.in_(user_ids),
                    )
                )
            ).scalars().all()
        }

    movements = []
    for r in rows:
        product = products_by_id.get(r.product_id)
        user = users_by_id.get(r.created_by) if r.created_by else None
        movements.append(
            {
                "id": r.id,
                "product_id": r.product_id,
                "product_sku": product.sku if product else None,
                "product_name": product.name if product else None,
                "warehouse_id": r.warehouse_id,
                "movement_type": r.movement_type,
                "quantity": float(r.quantity),
                "quantity_before": float(r.quantity_before),
                "quantity_after": float(r.quantity_after),
                "reference_type": r.reference_type,
                "reference_id": r.reference_id,
                "notes": r.notes,
                "reason": r.reason,
                "created_by": r.created_by,
                "created_by_name": user.full_name if user else None,
                "created_by_email": user.email if user else None,
                "created_at": r.created_at,
            }
        )

    return {
        "count": len(movements),
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "store_id": store_id,
        "store_name": store_name,
        "movement_type": movement_type,
        "created_by": created_by,
        "reason": reason,
        "movements": movements,
    }


async def inventory_low_stock(
    db: AsyncSession,
    tenant_id: str,
    *,
    store_id: str | None = None,
    warehouse_id: str | None = None,
) -> dict:
    """Product-level and optional store/warehouse reorder breaches."""
    products = (
        await db.execute(
            select(m.Product).where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active == True,  # noqa: E712
                m.Product.stock_qty <= m.Product.reorder_level,
            ).order_by(m.Product.stock_qty.asc())
        )
    ).scalars().all()
    product_rows = [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "stock_qty": float(p.stock_qty or 0),
            "reorder_level": float(p.reorder_level or 0),
            "suggested_order_qty": max(
                1.0, round(float(p.reorder_level or 0) - float(p.stock_qty or 0), 3)
            )
            if float(p.stock_qty or 0) <= float(p.reorder_level or 0)
            else 0.0,
            "scope": "product",
        }
        for p in products
    ]

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
            m.WarehouseStock.reorder_level > 0,
            m.WarehouseStock.quantity <= m.WarehouseStock.reorder_level,
        )
        .order_by(m.WarehouseStock.quantity.asc())
    )
    if wh_filter:
        stmt = stmt.where(m.WarehouseStock.warehouse_id == wh_filter)
    for stock, product, wh in (await db.execute(stmt)).all():
        qty = float(stock.quantity or 0)
        reorder = float(stock.reorder_level or 0)
        reorder_qty = float(stock.reorder_qty or 0)
        warehouse_rows.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": qty,
                "reorder_level": reorder,
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
    warehouse_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    """Batches nearing expiry (BR-14.2); optional warehouse/store filter."""
    from app import catalog as catalog_svc

    within_days = max(0, min(int(within_days), 3650))
    (
        warehouse_id,
        warehouse_name,
        store_id,
        store_name,
        warehouse_ids,
    ) = await _resolve_purchase_location_filters(
        db, tenant_id, warehouse_id=warehouse_id, store_id=store_id
    )

    batches = await catalog_svc.list_expiring_batches(
        db, tenant_id, within_days=within_days
    )
    if warehouse_ids is not None:
        allowed = set(warehouse_ids)
        batches = [b for b in batches if b.warehouse_id in allowed]

    product_ids = {b.product_id for b in batches}
    products: dict[str, m.Product] = {}
    if product_ids:
        for p in (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == tenant_id,
                    m.Product.id.in_(list(product_ids)),
                )
            )
        ).scalars().all():
            products[p.id] = p

    today = datetime.utcnow().date()
    rows: list[dict] = []
    expired_count = 0
    total_qty = 0.0
    for b in batches:
        product = products.get(b.product_id)
        exp = b.expiry_date.date() if b.expiry_date else None
        days_until = (exp - today).days if exp else None
        if days_until is not None and days_until < 0:
            expired_count += 1
        qty = float(b.quantity or 0)
        total_qty += qty
        row = catalog_svc.serialize_batch(b)
        row.update(
            {
                "sku": product.sku if product else None,
                "name": product.name if product else None,
                "days_until_expiry": days_until,
                "is_expired": bool(days_until is not None and days_until < 0),
            }
        )
        rows.append(row)

    return {
        "within_days": within_days,
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "store_id": store_id,
        "store_name": store_name,
        "count": len(rows),
        "expired_count": expired_count,
        "total_quantity": round(total_qty, 3),
        "batches": rows,
    }


TRANSFER_REPORT_STATUSES = frozenset(
    {"draft", "requested", "in_transit", "received", "cancelled"}
)


async def inventory_transfers(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    status: str | None = None,
    from_store_id: str | None = None,
    to_store_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    """Inter-store transfer history & reporting (BR-13.2 / BR-14.5).

    Optional ``store_id`` matches transfers where the store is source **or**
    destination. Directional ``from_store_id`` / ``to_store_id`` still apply.
    """
    from fastapi import HTTPException

    if status:
        key = status.strip().lower()
        if key not in TRANSFER_REPORT_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid transfer status '{key}'. "
                    f"Allowed: {sorted(TRANSFER_REPORT_STATUSES)}"
                ),
            )
        status = key

    store_name = None
    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.tenant_id == tenant_id,
                    m.Store.id == store_id,
                )
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        store_id = store.id
        store_name = store.name

    stores = {
        s.id: s
        for s in (
            await db.execute(select(m.Store).where(m.Store.tenant_id == tenant_id))
        ).scalars().all()
    }
    stmt = (
        select(m.StockTransfer)
        .where(m.StockTransfer.tenant_id == tenant_id)
        .order_by(m.StockTransfer.created_at.desc())
    )
    if status:
        stmt = stmt.where(m.StockTransfer.status == status)
    if store_id:
        stmt = stmt.where(
            or_(
                m.StockTransfer.from_store_id == store_id,
                m.StockTransfer.to_store_id == store_id,
            )
        )
    if from_store_id:
        stmt = stmt.where(m.StockTransfer.from_store_id == from_store_id)
    if to_store_id:
        stmt = stmt.where(m.StockTransfer.to_store_id == to_store_id)
    if from_date:
        stmt = stmt.where(m.StockTransfer.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.StockTransfer.created_at <= to_date)

    rows = (await db.execute(stmt)).scalars().all()
    by_status: dict[str, int] = defaultdict(int)
    by_route: dict[str, dict] = {}
    transfers: list[dict] = []
    total_qty = 0.0

    for xfer in rows:
        from_store = stores.get(xfer.from_store_id)
        to_store = stores.get(xfer.to_store_id)
        from_name = from_store.name if from_store else "Unknown"
        to_name = to_store.name if to_store else "Unknown"
        from_code = from_store.code if from_store else None
        to_code = to_store.code if to_store else None
        items = (
            await db.execute(
                select(m.StockTransferItem).where(
                    m.StockTransferItem.tenant_id == tenant_id,
                    m.StockTransferItem.transfer_id == xfer.id,
                )
            )
        ).scalars().all()
        qty = round(sum(float(i.quantity or 0) for i in items), 3)
        shipped_qty = round(sum(float(i.shipped_qty or 0) for i in items), 3)
        received_qty = round(sum(float(i.received_qty or 0) for i in items), 3)
        total_qty += qty
        by_status[xfer.status] += 1
        route_key = f"{xfer.from_store_id}->{xfer.to_store_id}"
        route = by_route.setdefault(
            route_key,
            {
                "from_store_id": xfer.from_store_id,
                "to_store_id": xfer.to_store_id,
                "from_store_code": from_code,
                "to_store_code": to_code,
                "from_store_name": from_name,
                "to_store_name": to_name,
                "transfer_count": 0,
                "quantity": 0.0,
            },
        )
        route["transfer_count"] += 1
        route["quantity"] = round(route["quantity"] + qty, 3)

        transfers.append(
            {
                "id": xfer.id,
                "transfer_number": xfer.transfer_number,
                "from_store_id": xfer.from_store_id,
                "to_store_id": xfer.to_store_id,
                "from_store_code": from_code,
                "to_store_code": to_code,
                "from_store_name": from_name,
                "to_store_name": to_name,
                "from_warehouse_id": xfer.from_warehouse_id,
                "to_warehouse_id": xfer.to_warehouse_id,
                "status": xfer.status,
                "quantity": qty,
                "shipped_qty": shipped_qty,
                "received_qty": received_qty,
                "line_count": len(items),
                "shipped_at": xfer.shipped_at,
                "received_at": xfer.received_at,
                "created_at": xfer.created_at,
                "notes": xfer.notes,
            }
        )

    routes = sorted(by_route.values(), key=lambda x: x["transfer_count"], reverse=True)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "status": status,
        "store_id": store_id,
        "store_name": store_name,
        "from_store_id": from_store_id,
        "to_store_id": to_store_id,
        "transfer_count": len(transfers),
        "total_quantity": round(total_qty, 3),
        "by_status": dict(by_status),
        "by_route": routes,
        "transfers": transfers,
    }


async def _resolve_purchase_location_filters(
    db: AsyncSession,
    tenant_id: str,
    *,
    warehouse_id: str | None = None,
    store_id: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None, list[str] | None]:
    """Validate optional warehouse/store filters for purchase reports.

    Returns (warehouse_id, warehouse_name, store_id, store_name, warehouse_ids).
    ``warehouse_ids`` is None when no location filter; otherwise the PO.warehouse_id
    values that match (empty list means no matching warehouses / no rows).
    """
    from fastapi import HTTPException

    warehouse_name = None
    store_name = None
    warehouse_ids: list[str] | None = None

    if warehouse_id:
        wh = (
            await db.execute(
                select(m.Warehouse).where(
                    m.Warehouse.tenant_id == tenant_id,
                    m.Warehouse.id == warehouse_id,
                )
            )
        ).scalar_one_or_none()
        if not wh:
            raise HTTPException(status_code=404, detail="Warehouse not found")
        if store_id and wh.store_id and wh.store_id != store_id:
            raise HTTPException(
                status_code=400,
                detail="Warehouse does not belong to the selected store",
            )
        warehouse_id = wh.id
        warehouse_name = wh.name
        if wh.store_id and not store_id:
            store_id = wh.store_id
        warehouse_ids = [wh.id]

    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.tenant_id == tenant_id,
                    m.Store.id == store_id,
                )
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        store_id = store.id
        store_name = store.name
        if warehouse_ids is None:
            whs = (
                await db.execute(
                    select(m.Warehouse).where(
                        m.Warehouse.tenant_id == tenant_id,
                        m.Warehouse.store_id == store_id,
                    )
                )
            ).scalars().all()
            warehouse_ids = [w.id for w in whs]

    return warehouse_id, warehouse_name, store_id, store_name, warehouse_ids


async def purchases_summary(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    warehouse_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    (
        warehouse_id,
        warehouse_name,
        store_id,
        store_name,
        warehouse_ids,
    ) = await _resolve_purchase_location_filters(
        db, tenant_id, warehouse_id=warehouse_id, store_id=store_id
    )
    stmt = select(m.PurchaseOrder).where(
        m.PurchaseOrder.tenant_id == tenant_id,
        m.PurchaseOrder.status != "cancelled",
    )
    if from_date:
        stmt = stmt.where(m.PurchaseOrder.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.PurchaseOrder.created_at <= to_date)
    if warehouse_ids is not None:
        if not warehouse_ids:
            stmt = stmt.where(m.PurchaseOrder.id == None)  # noqa: E711
        else:
            stmt = stmt.where(m.PurchaseOrder.warehouse_id.in_(warehouse_ids))
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
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "store_id": store_id,
        "store_name": store_name,
        "order_count": len(orders),
        "total_amount": round(total, 2),
        "outstanding_amount": round(pending, 2),
        "by_status": dict(by_status),
    }


PENDING_PO_STATUSES = frozenset({"draft", "sent", "partially_received"})


async def purchases_pending_orders(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    supplier_id: str | None = None,
    status: str | None = None,
    warehouse_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    """POs not yet fully received (BR-14.3 Pending Orders).

    Includes draft / sent / partially_received. Excludes received and cancelled.
    """
    (
        warehouse_id,
        warehouse_name,
        store_id,
        store_name,
        warehouse_ids,
    ) = await _resolve_purchase_location_filters(
        db, tenant_id, warehouse_id=warehouse_id, store_id=store_id
    )
    statuses = PENDING_PO_STATUSES
    if status:
        key = status.strip().lower()
        if key not in PENDING_PO_STATUSES:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid pending status '{key}'. "
                    f"Allowed: {sorted(PENDING_PO_STATUSES)}"
                ),
            )
        statuses = frozenset({key})

    stmt = (
        select(m.PurchaseOrder, m.Party)
        .join(m.Party, m.Party.id == m.PurchaseOrder.supplier_id)
        .where(
            m.PurchaseOrder.tenant_id == tenant_id,
            m.PurchaseOrder.status.in_(tuple(statuses)),
        )
        .order_by(m.PurchaseOrder.created_at.desc())
    )
    if supplier_id:
        stmt = stmt.where(m.PurchaseOrder.supplier_id == supplier_id)
    if from_date:
        stmt = stmt.where(m.PurchaseOrder.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.PurchaseOrder.created_at <= to_date)
    if warehouse_ids is not None:
        if not warehouse_ids:
            stmt = stmt.where(m.PurchaseOrder.id == None)  # noqa: E711
        else:
            stmt = stmt.where(m.PurchaseOrder.warehouse_id.in_(warehouse_ids))

    rows = (await db.execute(stmt)).all()
    orders: list[dict] = []
    by_status: dict[str, int] = defaultdict(int)
    total_amount = 0.0
    total_outstanding_qty = 0.0

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
        outstanding_qty = round(max(ordered_qty - received_qty, 0), 3)
        amount = float(po.total_amount or 0)
        by_status[po.status] += 1
        total_amount += amount
        total_outstanding_qty += outstanding_qty
        orders.append(
            {
                "id": po.id,
                "po_number": po.po_number,
                "supplier_id": party.id,
                "supplier_name": party.name,
                "status": po.status,
                "warehouse_id": po.warehouse_id,
                "total_amount": amount,
                "ordered_qty": ordered_qty,
                "received_qty": received_qty,
                "outstanding_qty": outstanding_qty,
                "due_date": po.due_date,
                "created_at": po.created_at,
                "line_count": len(items),
            }
        )

    return {
        "from_date": from_date,
        "to_date": to_date,
        "supplier_id": supplier_id,
        "status": status,
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "store_id": store_id,
        "store_name": store_name,
        "order_count": len(orders),
        "total_amount": round(total_amount, 2),
        "total_outstanding_qty": round(total_outstanding_qty, 3),
        "by_status": dict(by_status),
        "orders": orders,
    }


async def purchases_returns_summary(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    supplier_id: str | None = None,
    reason: str | None = None,
    status: str | None = None,
    warehouse_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    """Purchase return summary by period / reason / supplier (BR-14.3).

    Optional ``warehouse_id`` / ``store_id`` scopes by ``PurchaseReturn.warehouse_id``
    (same location resolver as other purchase reports).
    """
    from app.purchasing import PURCHASE_RETURN_REASONS

    (
        warehouse_id,
        warehouse_name,
        store_id,
        store_name,
        warehouse_ids,
    ) = await _resolve_purchase_location_filters(
        db, tenant_id, warehouse_id=warehouse_id, store_id=store_id
    )

    if reason:
        key = reason.strip().lower()
        if key not in PURCHASE_RETURN_REASONS:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail=f"reason must be one of {sorted(PURCHASE_RETURN_REASONS)}",
            )
        reason = key
    if status:
        status = status.strip().lower()
        if status not in {"draft", "posted", "cancelled"}:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail="status must be draft, posted, or cancelled",
            )

    stmt = (
        select(m.PurchaseReturn, m.Party)
        .join(m.Party, m.Party.id == m.PurchaseReturn.supplier_id)
        .where(m.PurchaseReturn.tenant_id == tenant_id)
        .order_by(m.PurchaseReturn.created_at.desc())
    )
    if supplier_id:
        stmt = stmt.where(m.PurchaseReturn.supplier_id == supplier_id)
    if reason:
        stmt = stmt.where(m.PurchaseReturn.reason == reason)
    if status:
        stmt = stmt.where(m.PurchaseReturn.status == status)
    if from_date:
        stmt = stmt.where(m.PurchaseReturn.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.PurchaseReturn.created_at <= to_date)
    if warehouse_ids is not None:
        if not warehouse_ids:
            stmt = stmt.where(m.PurchaseReturn.id == None)  # noqa: E711
        else:
            stmt = stmt.where(m.PurchaseReturn.warehouse_id.in_(warehouse_ids))

    rows = (await db.execute(stmt)).all()
    by_reason: dict[str, dict] = {}
    by_status: dict[str, int] = defaultdict(int)
    by_supplier: dict[str, dict] = {}
    returns: list[dict] = []
    total_amount = 0.0
    posted_amount = 0.0
    total_qty = 0.0

    for ret, party in rows:
        items = (
            await db.execute(
                select(m.PurchaseReturnItem).where(
                    m.PurchaseReturnItem.tenant_id == tenant_id,
                    m.PurchaseReturnItem.purchase_return_id == ret.id,
                )
            )
        ).scalars().all()
        qty = round(sum(float(i.quantity or 0) for i in items), 3)
        amount = float(ret.total_amount or 0)
        total_amount += amount
        total_qty += qty
        by_status[ret.status] += 1
        if ret.status == "posted":
            posted_amount += amount

        reason_row = by_reason.setdefault(
            ret.reason or "other",
            {"reason": ret.reason or "other", "return_count": 0, "total_amount": 0.0, "quantity": 0.0},
        )
        reason_row["return_count"] += 1
        reason_row["total_amount"] = round(reason_row["total_amount"] + amount, 2)
        reason_row["quantity"] = round(reason_row["quantity"] + qty, 3)

        sup = by_supplier.setdefault(
            party.id,
            {
                "supplier_id": party.id,
                "name": party.name,
                "return_count": 0,
                "total_amount": 0.0,
                "quantity": 0.0,
            },
        )
        sup["return_count"] += 1
        sup["total_amount"] = round(sup["total_amount"] + amount, 2)
        sup["quantity"] = round(sup["quantity"] + qty, 3)

        returns.append(
            {
                "id": ret.id,
                "return_number": ret.return_number,
                "debit_note_number": ret.debit_note_number,
                "supplier_id": party.id,
                "supplier_name": party.name,
                "status": ret.status,
                "reason": ret.reason,
                "quantity": qty,
                "subtotal": float(ret.subtotal or 0),
                "tax_amount": float(ret.tax_amount or 0),
                "total_amount": amount,
                "goods_receipt_id": ret.goods_receipt_id,
                "purchase_order_id": ret.purchase_order_id,
                "posted_at": ret.posted_at,
                "created_at": ret.created_at,
            }
        )

    reasons = sorted(by_reason.values(), key=lambda x: x["total_amount"], reverse=True)
    suppliers = sorted(by_supplier.values(), key=lambda x: x["total_amount"], reverse=True)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "supplier_id": supplier_id,
        "reason": reason,
        "status": status,
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "store_id": store_id,
        "store_name": store_name,
        "return_count": len(returns),
        "total_amount": round(total_amount, 2),
        "posted_amount": round(posted_amount, 2),
        "total_quantity": round(total_qty, 3),
        "by_status": dict(by_status),
        "by_reason": reasons,
        "by_supplier": suppliers,
        "returns": returns,
    }


async def purchases_by_supplier(
    db: AsyncSession,
    tenant_id: str,
    *,
    supplier_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    warehouse_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    (
        warehouse_id,
        warehouse_name,
        store_id,
        store_name,
        warehouse_ids,
    ) = await _resolve_purchase_location_filters(
        db, tenant_id, warehouse_id=warehouse_id, store_id=store_id
    )
    stmt = select(m.PurchaseOrder, m.Party).join(m.Party, m.Party.id == m.PurchaseOrder.supplier_id).where(
        m.PurchaseOrder.tenant_id == tenant_id,
        m.PurchaseOrder.status != "cancelled",
    )
    if supplier_id:
        stmt = stmt.where(m.PurchaseOrder.supplier_id == supplier_id)
    if from_date:
        stmt = stmt.where(m.PurchaseOrder.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.PurchaseOrder.created_at <= to_date)
    if warehouse_ids is not None:
        if not warehouse_ids:
            stmt = stmt.where(m.PurchaseOrder.id == None)  # noqa: E711
        else:
            stmt = stmt.where(m.PurchaseOrder.warehouse_id.in_(warehouse_ids))
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
    return {
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "store_id": store_id,
        "store_name": store_name,
        "suppliers": suppliers,
        "total_amount": round(sum(s["total_amount"] for s in suppliers), 2),
    }


async def expenses_summary(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    category_id: str | None = None,
    branch_id: str | None = None,
    department_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    (
        branch_id,
        branch_name,
        department_id,
        department_name,
        store_id,
        store_name,
    ) = await _resolve_expense_org_filters(
        db,
        tenant_id,
        branch_id=branch_id,
        department_id=department_id,
        store_id=store_id,
    )
    stmt = select(m.Expense).where(
        m.Expense.tenant_id == tenant_id,
        m.Expense.status == "approved",
    )
    if category_id:
        stmt = stmt.where(m.Expense.category_id == category_id)
    if from_date:
        stmt = stmt.where(m.Expense.expense_date >= from_date)
    if to_date:
        stmt = stmt.where(m.Expense.expense_date <= to_date)
    if branch_id:
        stmt = stmt.where(m.Expense.branch_id == branch_id)
    if department_id:
        stmt = stmt.where(m.Expense.department_id == department_id)
    if store_id:
        stmt = stmt.where(m.Expense.store_id == store_id)
    rows = (await db.execute(stmt)).scalars().all()
    by_category: dict[str, float] = defaultdict(float)
    for e in rows:
        by_category[e.category or "Uncategorized"] += float(e.amount or 0)
    categories = [
        {"category": k, "amount": round(v, 2)}
        for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)
    ]
    return {
        "count": len(rows),
        "total_amount": round(sum(float(e.amount or 0) for e in rows), 2),
        "by_category": categories,
        "branch_id": branch_id,
        "branch_name": branch_name,
        "department_id": department_id,
        "department_name": department_name,
        "store_id": store_id,
        "store_name": store_name,
    }


async def _resolve_expense_org_filters(
    db: AsyncSession,
    tenant_id: str,
    *,
    branch_id: str | None = None,
    department_id: str | None = None,
    store_id: str | None = None,
) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    """Validate optional branch/department/store filters.

    Returns (branch_id, branch_name, dept_id, dept_name, store_id, store_name).
    """
    from fastapi import HTTPException

    branch_name = None
    dept_name = None
    store_name = None
    if branch_id:
        branch = (
            await db.execute(
                select(m.Branch).where(
                    m.Branch.tenant_id == tenant_id,
                    m.Branch.id == branch_id,
                )
            )
        ).scalar_one_or_none()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        branch_id = branch.id
        branch_name = branch.name
    if department_id:
        dept = (
            await db.execute(
                select(m.Department).where(
                    m.Department.tenant_id == tenant_id,
                    m.Department.id == department_id,
                )
            )
        ).scalar_one_or_none()
        if not dept:
            raise HTTPException(status_code=404, detail="Department not found")
        if branch_id and dept.branch_id and dept.branch_id != branch_id:
            raise HTTPException(
                status_code=400,
                detail="Department does not belong to the selected branch",
            )
        department_id = dept.id
        dept_name = dept.name
    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.tenant_id == tenant_id,
                    m.Store.id == store_id,
                )
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        if branch_id and store.branch_id and store.branch_id != branch_id:
            raise HTTPException(
                status_code=400,
                detail="Store does not belong to the selected branch",
            )
        store_id = store.id
        store_name = store.name
    return branch_id, branch_name, department_id, dept_name, store_id, store_name


def _expense_period_days(
    from_date: datetime | None, to_date: datetime | None
) -> int:
    if from_date and to_date:
        return max(1, (to_date.date() - from_date.date()).days + 1)
    return 30


async def budget_vs_actual(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    category_id: str | None = None,
    branch_id: str | None = None,
    department_id: str | None = None,
    store_id: str | None = None,
) -> dict:
    """Monthly category budgets scaled to the period vs approved spend (BR-9.1 / BR-14.4)."""
    from app.expenses import ensure_default_categories, scale_monthly_budget

    await ensure_default_categories(db, tenant_id)
    period_days = _expense_period_days(from_date, to_date)
    (
        branch_id,
        branch_name,
        department_id,
        department_name,
        store_id,
        store_name,
    ) = await _resolve_expense_org_filters(
        db,
        tenant_id,
        branch_id=branch_id,
        department_id=department_id,
        store_id=store_id,
    )

    cat_stmt = select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tenant_id)
    if category_id:
        cat_stmt = cat_stmt.where(m.ExpenseCategory.id == category_id)
    categories = (await db.execute(cat_stmt.order_by(m.ExpenseCategory.name))).scalars().all()

    exp_stmt = select(m.Expense).where(
        m.Expense.tenant_id == tenant_id,
        m.Expense.status == "approved",
    )
    if category_id:
        exp_stmt = exp_stmt.where(m.Expense.category_id == category_id)
    if from_date:
        exp_stmt = exp_stmt.where(m.Expense.expense_date >= from_date)
    if to_date:
        exp_stmt = exp_stmt.where(m.Expense.expense_date <= to_date)
    if branch_id:
        exp_stmt = exp_stmt.where(m.Expense.branch_id == branch_id)
    if department_id:
        exp_stmt = exp_stmt.where(m.Expense.department_id == department_id)
    if store_id:
        exp_stmt = exp_stmt.where(m.Expense.store_id == store_id)
    expenses = (await db.execute(exp_stmt)).scalars().all()

    actual_by_id: dict[str, float] = defaultdict(float)
    uncategorized = 0.0
    for e in expenses:
        amt = float(e.amount or 0)
        if e.category_id:
            actual_by_id[e.category_id] += amt
        else:
            uncategorized += amt

    rows_out: list[dict] = []
    total_budget = 0.0
    total_actual = 0.0
    for cat in categories:
        budget_monthly = float(cat.budget_amount or 0)
        scaled = scale_monthly_budget(budget_monthly, period_days)
        actual = float(actual_by_id.get(cat.id, 0))
        if not cat.is_active and actual <= 0 and budget_monthly <= 0:
            continue
        if budget_monthly <= 0:
            status = "no_budget"
            variance = actual
            variance_pct = None
        else:
            variance = actual - scaled
            variance_pct = round((variance / scaled) * 100.0, 1) if scaled else 0.0
            if abs(variance) < 0.01:
                status = "on_budget"
            elif variance > 0:
                status = "over_budget"
            else:
                status = "under_budget"
        total_budget += scaled if budget_monthly > 0 else 0.0
        total_actual += actual
        rows_out.append(
            {
                "category_id": cat.id,
                "code": cat.code,
                "category": cat.name,
                "budget_monthly": round(budget_monthly, 2),
                "budget_scaled": round(scaled, 2) if budget_monthly > 0 else 0.0,
                "actual": round(actual, 2),
                "variance": round(variance, 2),
                "variance_pct": variance_pct,
                "status": status,
                "is_active": bool(cat.is_active),
            }
        )

    if uncategorized > 0 and not category_id:
        total_actual += uncategorized
        rows_out.append(
            {
                "category_id": None,
                "code": None,
                "category": "Uncategorized",
                "budget_monthly": 0.0,
                "budget_scaled": 0.0,
                "actual": round(uncategorized, 2),
                "variance": round(uncategorized, 2),
                "variance_pct": None,
                "status": "no_budget",
                "is_active": True,
            }
        )

    rows_out.sort(key=lambda r: (-float(r["actual"]), r["category"] or ""))
    top_categories = rows_out[:5]
    total_variance = total_actual - total_budget
    return {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "period_days": period_days,
        "total_budget_scaled": round(total_budget, 2),
        "total_actual": round(total_actual, 2),
        "total_variance": round(total_variance, 2),
        "top_categories": top_categories,
        "rows": rows_out,
        "branch_id": branch_id,
        "branch_name": branch_name,
        "department_id": department_id,
        "department_name": department_name,
        "store_id": store_id,
        "store_name": store_name,
    }


_CF_FINANCING_TYPES = frozenset({"coa_opening"})
_CF_INVESTING_TYPES = frozenset()  # reserved for CapEx / fixed-asset sources


def _empty_cf_bucket() -> dict:
    return {"inflows": 0.0, "outflows": 0.0, "net": 0.0}


def _round_cf_bucket(bucket: dict) -> dict:
    return {
        "inflows": round(float(bucket["inflows"]), 2),
        "outflows": round(float(bucket["outflows"]), 2),
        "net": round(float(bucket["inflows"]) - float(bucket["outflows"]), 2),
    }


def cash_flow_activity(
    source_type: str | None,
    *,
    transfer_kind: str | None = None,
) -> str:
    """Classify a liquid-GL journal into operating|investing|financing|transfers (BR-10.6)."""
    st = (source_type or "").strip().lower()
    if st == "cash_transfer":
        kind = (transfer_kind or "transfer").strip().lower()
        if kind in {"deposit", "withdrawal"}:
            return "financing"
        return "transfers"
    if st in _CF_FINANCING_TYPES:
        return "financing"
    if st in _CF_INVESTING_TYPES:
        return "investing"
    # Default unknown/blank to operating (conservative for working-capital cash)
    return "operating"


async def cash_flow(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    branch_id: str | None = None,
) -> dict:
    """Cash flow from cash + bank GL accounts with O/I/F sections (BR-10.6 / BR-14.5).

    Optional ``store_id`` / ``branch_id`` restrict lines to journals attributable to that
    location (expenses, POS, sales returns, customer payments on store invoices). Unlocated
    financing/transfers (e.g. ``cash_transfer``, ``coa_opening``) are omitted when filtered.
    """
    from app.accounting import (
        _pnl_journal_ids_for_stores,
        _pnl_store_ids,
        ensure_default_accounts,
    )

    empty_sections = {
        "operating": _round_cf_bucket(_empty_cf_bucket()),
        "investing": _round_cf_bucket(_empty_cf_bucket()),
        "financing": _round_cf_bucket(_empty_cf_bucket()),
        "transfers": _round_cf_bucket(_empty_cf_bucket()),
    }
    store_ids = await _pnl_store_ids(
        db, tenant_id, store_id=store_id, branch_id=branch_id
    )
    location_filter = store_ids is not None
    allowed_journal_ids: set[str] | None = None
    if location_filter:
        allowed_journal_ids = await _cf_journal_ids_for_location(
            db,
            tenant_id,
            store_ids or [],
            branch_id=branch_id,
            pnl_helper=_pnl_journal_ids_for_stores,
        )

    await ensure_default_accounts(db, tenant_id)
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
    if not liquid:
        return {
            "inflows": 0,
            "outflows": 0,
            "net": 0,
            **empty_sections,
            "lines": [],
            "accounts": [],
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "store_id": store_id,
            "branch_id": branch_id,
            "mode": "journals" if location_filter or from_date or to_date else "all",
        }

    account_ids = [a.id for a in liquid]
    by_id = {a.id: a for a in liquid}
    stmt = (
        select(m.JournalEntryLine, m.JournalEntry)
        .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntry.tenant_id == tenant_id,
            m.JournalEntry.status == "posted",
            m.JournalEntryLine.account_id.in_(account_ids),
        )
    )
    if from_date:
        stmt = stmt.where(m.JournalEntry.entry_date >= from_date)
    if to_date:
        stmt = stmt.where(m.JournalEntry.entry_date <= to_date)
    if allowed_journal_ids is not None:
        if not allowed_journal_ids:
            return {
                "inflows": 0,
                "outflows": 0,
                "net": 0,
                **empty_sections,
                "lines": [],
                "accounts": [{"id": a.id, "code": a.code, "name": a.name} for a in liquid],
                "from_date": from_date.isoformat() if from_date else None,
                "to_date": to_date.isoformat() if to_date else None,
                "store_id": store_id,
                "branch_id": branch_id,
                "mode": "journals",
            }
        stmt = stmt.where(m.JournalEntry.id.in_(allowed_journal_ids))
    rows = (await db.execute(stmt.order_by(m.JournalEntry.entry_date.asc()))).all()

    transfer_ids = {
        entry.source_id
        for _line, entry in rows
        if (entry.source_type or "").strip().lower() == "cash_transfer" and entry.source_id
    }
    transfer_kinds: dict[str, str] = {}
    if transfer_ids:
        for tid, kind in (
            await db.execute(
                select(m.CashTransfer.id, m.CashTransfer.kind).where(
                    m.CashTransfer.tenant_id == tenant_id,
                    m.CashTransfer.id.in_(transfer_ids),
                )
            )
        ).all():
            transfer_kinds[tid] = kind

    buckets = {
        "operating": _empty_cf_bucket(),
        "investing": _empty_cf_bucket(),
        "financing": _empty_cf_bucket(),
        "transfers": _empty_cf_bucket(),
    }
    inflows = 0.0
    outflows = 0.0
    lines = []
    for line, entry in rows:
        debit = float(line.debit or 0)
        credit = float(line.credit or 0)
        inflows += debit
        outflows += credit
        activity = cash_flow_activity(
            entry.source_type,
            transfer_kind=transfer_kinds.get(entry.source_id or ""),
        )
        buckets[activity]["inflows"] += debit
        buckets[activity]["outflows"] += credit
        acct = by_id.get(line.account_id)
        lines.append(
            {
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
        )
    return {
        "inflows": round(inflows, 2),
        "outflows": round(outflows, 2),
        "net": round(inflows - outflows, 2),
        "operating": _round_cf_bucket(buckets["operating"]),
        "investing": _round_cf_bucket(buckets["investing"]),
        "financing": _round_cf_bucket(buckets["financing"]),
        "transfers": _round_cf_bucket(buckets["transfers"]),
        "lines": lines,
        "accounts": [{"id": a.id, "code": a.code, "name": a.name} for a in liquid],
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "store_id": store_id,
        "branch_id": branch_id,
        "mode": "journals" if location_filter or from_date or to_date else "all",
    }


async def _cf_journal_ids_for_location(
    db: AsyncSession,
    tenant_id: str,
    store_ids: list[str],
    *,
    branch_id: str | None,
    pnl_helper,
) -> set[str]:
    """Posted journals whose liquid lines are attributable to store/branch (BR-14.5)."""
    ids: set[str] = set(
        await pnl_helper(db, tenant_id, store_ids, branch_id=branch_id)
    )
    # Customer payments against invoices at these stores
    if store_ids:
        pay_ids = set(
            (
                await db.execute(
                    select(m.CustomerPayment.id)
                    .join(
                        m.SalesInvoice,
                        m.SalesInvoice.id == m.CustomerPayment.sales_invoice_id,
                    )
                    .where(
                        m.CustomerPayment.tenant_id == tenant_id,
                        m.SalesInvoice.tenant_id == tenant_id,
                        m.SalesInvoice.store_id.in_(store_ids),
                    )
                )
            ).scalars().all()
        )
        if pay_ids:
            rows = (
                await db.execute(
                    select(m.JournalEntry.id).where(
                        m.JournalEntry.tenant_id == tenant_id,
                        m.JournalEntry.status == "posted",
                        m.JournalEntry.source_type == "customer_payment",
                        m.JournalEntry.source_id.in_(pay_ids),
                    )
                )
            ).scalars().all()
            ids.update(rows)
    return ids


def _prior_period_end(as_of_day) -> datetime:
    """Last calendar day of the month before as_of."""
    first = as_of_day.replace(day=1)
    prior = first - timedelta(days=1)
    return datetime(prior.year, prior.month, prior.day, 23, 59, 59, 999999)


def _prior_year_end(as_of_day) -> datetime:
    try:
        prior = as_of_day.replace(year=as_of_day.year - 1)
    except ValueError:
        prior = as_of_day.replace(year=as_of_day.year - 1, day=28)
    return datetime(prior.year, prior.month, prior.day, 23, 59, 59, 999999)


def _pack_balance_sheet(
    *,
    as_of_day,
    mode: str,
    assets: list[dict],
    liabilities: list[dict],
    equity: list[dict],
    compare: dict | None = None,
) -> dict:
    total_assets = round(sum(float(r["balance"]) for r in assets), 2)
    total_liabilities = round(sum(float(r["balance"]) for r in liabilities), 2)
    total_equity = round(sum(float(r["balance"]) for r in equity), 2)
    total_le = round(total_liabilities + total_equity, 2)
    payload = {
        "as_of": as_of_day.isoformat() if hasattr(as_of_day, "isoformat") else str(as_of_day),
        "mode": mode,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_liabilities_and_equity": total_le,
        "balanced": abs(total_assets - total_le) < 0.01,
        "compare": compare,
    }
    return payload


def _merge_bs_compare(current: dict, prior: dict, compare_mode: str) -> dict:
    """Attach prior balances / deltas onto current BS sections."""

    def merge_section(cur_rows: list[dict], prior_rows: list[dict]) -> list[dict]:
        prior_by = {r["code"]: float(r["balance"]) for r in prior_rows}
        seen = set()
        out = []
        for r in cur_rows:
            code = r["code"]
            seen.add(code)
            prior_bal = prior_by.get(code, 0.0)
            bal = float(r["balance"])
            out.append(
                {
                    **r,
                    "prior_balance": round(prior_bal, 2),
                    "delta": round(bal - prior_bal, 2),
                }
            )
        for r in prior_rows:
            if r["code"] in seen:
                continue
            prior_bal = float(r["balance"])
            out.append(
                {
                    "code": r["code"],
                    "name": r["name"],
                    "balance": 0.0,
                    "prior_balance": round(prior_bal, 2),
                    "delta": round(0.0 - prior_bal, 2),
                }
            )
        return out

    assets = merge_section(current["assets"], prior["assets"])
    liabilities = merge_section(current["liabilities"], prior["liabilities"])
    equity = merge_section(current["equity"], prior["equity"])
    compare = {
        "mode": compare_mode,
        "as_of": prior["as_of"],
        "total_assets": prior["total_assets"],
        "total_liabilities": prior["total_liabilities"],
        "total_equity": prior["total_equity"],
        "total_liabilities_and_equity": prior["total_liabilities_and_equity"],
        "deltas": {
            "total_assets": round(
                float(current["total_assets"]) - float(prior["total_assets"]), 2
            ),
            "total_liabilities": round(
                float(current["total_liabilities"]) - float(prior["total_liabilities"]), 2
            ),
            "total_equity": round(
                float(current["total_equity"]) - float(prior["total_equity"]), 2
            ),
            "total_liabilities_and_equity": round(
                float(current["total_liabilities_and_equity"])
                - float(prior["total_liabilities_and_equity"]),
                2,
            ),
        },
    }
    return _pack_balance_sheet(
        as_of_day=current["as_of"],
        mode=current["mode"],
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        compare=compare,
    )


async def _balance_sheet_at(
    db: AsyncSession,
    tenant_id: str,
    *,
    as_of: datetime | None,
) -> dict:
    """Build BS at as_of from posted journals, or live balances when as_of is None."""
    from app.accounting import _signed_balance_delta, ensure_default_accounts

    await ensure_default_accounts(db, tenant_id)
    accounts = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id).order_by(m.Account.code)
        )
    ).scalars().all()

    if as_of is None:
        bal_by_id = {a.id: float(a.balance or 0) for a in accounts}
        as_of_day = datetime.utcnow().date()
        mode = "balances"
    else:
        bal_by_id = {a.id: 0.0 for a in accounts}
        stmt = (
            select(m.JournalEntryLine, m.Account)
            .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
            .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
            .where(
                m.JournalEntryLine.tenant_id == tenant_id,
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.status == "posted",
                m.JournalEntry.entry_date <= as_of,
                m.Account.tenant_id == tenant_id,
            )
        )
        for line, account in (await db.execute(stmt)).all():
            bal_by_id[account.id] = float(bal_by_id.get(account.id, 0)) + _signed_balance_delta(
                account.account_type,
                float(line.debit or 0),
                float(line.credit or 0),
            )
        as_of_day = as_of.date()
        mode = "journals"

    def rows_for(account_type: str) -> list[dict]:
        rows = []
        for a in accounts:
            if a.account_type != account_type:
                continue
            bal = round(float(bal_by_id.get(a.id, 0)), 2)
            # Live balances mode keeps zero rows (back-compat); journal as-of omits zeros.
            if mode == "journals" and abs(bal) < 0.0001:
                continue
            rows.append({"code": a.code, "name": a.name, "balance": bal})
        return rows

    assets = rows_for("asset")
    liabilities = rows_for("liability")
    equity = rows_for("equity")
    income = sum(
        float(bal_by_id.get(a.id, 0)) for a in accounts if a.account_type == "income"
    )
    expense = sum(
        float(bal_by_id.get(a.id, 0)) for a in accounts if a.account_type == "expense"
    )
    retained = round(income - expense, 2)
    if abs(retained) > 0.0001:
        equity = [
            *equity,
            {"code": "RE", "name": "Retained earnings (computed)", "balance": retained},
        ]

    return _pack_balance_sheet(
        as_of_day=as_of_day,
        mode=mode,
        assets=assets,
        liabilities=liabilities,
        equity=equity,
        compare=None,
    )


async def balance_sheet(
    db: AsyncSession,
    tenant_id: str,
    *,
    as_of: datetime | None = None,
    compare: str | None = None,
) -> dict:
    """Point-in-time balance sheet (BR-14.5).

    - No ``as_of`` / compare: live ``Account.balance`` (back-compat, ``mode=balances``).
    - With ``as_of``: reconstruct from posted journal lines through that timestamp.
    - ``compare=prior_period|prior_year``: side-by-side prior balances and deltas.
      When compare is set without ``as_of``, uses end of today.
    """
    compare_mode = (compare or "").strip().lower() or None
    if compare_mode and compare_mode not in {"prior_period", "prior_year"}:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail="compare must be prior_period or prior_year",
        )

    effective_as_of = as_of
    if compare_mode and effective_as_of is None:
        today = datetime.utcnow().date()
        effective_as_of = datetime(
            today.year, today.month, today.day, 23, 59, 59, 999999
        )

    current = await _balance_sheet_at(db, tenant_id, as_of=effective_as_of)
    if not compare_mode:
        return current

    as_of_day = parse_date(current["as_of"])
    if as_of_day is None:
        as_of_day = datetime.utcnow()
    day = as_of_day.date() if isinstance(as_of_day, datetime) else as_of_day
    if compare_mode == "prior_year":
        prior_dt = _prior_year_end(day)
    else:
        prior_dt = _prior_period_end(day)
    prior = await _balance_sheet_at(db, tenant_id, as_of=prior_dt)
    return _merge_bs_compare(current, prior, compare_mode)
