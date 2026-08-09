"""Operational and financial report aggregations."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
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


async def sales_daily(db: AsyncSession, tenant_id: str, date: datetime | None = None) -> dict:
    day = date or datetime.utcnow()
    start, end = day_bounds(day)

    invoices = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
                m.SalesInvoice.posted_at >= start,
                m.SalesInvoice.posted_at <= end,
            )
        )
    ).scalars().all()
    pos = (
        await db.execute(
            select(m.Transaction).where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
                m.Transaction.created_at >= start,
                m.Transaction.created_at <= end,
            )
        )
    ).scalars().all()

    invoice_total = sum(float(i.total_amount or 0) for i in invoices)
    invoice_tax = sum(float(i.tax_amount or 0) for i in invoices)
    invoice_discount = sum(float(i.discount_amount or 0) for i in invoices)
    pos_total = sum(float(t.total or 0) for t in pos)
    pos_tax = sum(float(t.tax or 0) for t in pos)

    return {
        "date": start.date().isoformat(),
        "invoice_count": len(invoices),
        "pos_count": len(pos),
        "invoice_revenue": round(invoice_total, 2),
        "pos_revenue": round(pos_total, 2),
        "total_revenue": round(invoice_total + pos_total, 2),
        "tax": round(invoice_tax + pos_tax, 2),
        "discounts": round(invoice_discount, 2),
        "net_sales": round(invoice_total + pos_total - invoice_discount, 2),
    }


async def sales_monthly(db: AsyncSession, tenant_id: str, year: int, month: int) -> dict:
    start, end = month_bounds(year, month)
    invoices = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
                m.SalesInvoice.posted_at >= start,
                m.SalesInvoice.posted_at <= end,
            )
        )
    ).scalars().all()
    pos = (
        await db.execute(
            select(m.Transaction).where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
                m.Transaction.created_at >= start,
                m.Transaction.created_at <= end,
            )
        )
    ).scalars().all()

    by_day: dict[str, float] = defaultdict(float)
    for inv in invoices:
        key = (inv.posted_at or inv.created_at).date().isoformat()
        by_day[key] += float(inv.total_amount or 0)
    for tx in pos:
        key = tx.created_at.date().isoformat()
        by_day[key] += float(tx.total or 0)

    total = sum(by_day.values())
    prev_year, prev_month = (year - 1, month) if month == 1 else (year, month - 1)
    prev = await sales_monthly_total(db, tenant_id, prev_year, prev_month)
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


async def sales_monthly_total(db: AsyncSession, tenant_id: str, year: int, month: int) -> float:
    start, end = month_bounds(year, month)
    inv = float(
        (
            await db.execute(
                select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                    m.SalesInvoice.tenant_id == tenant_id,
                    m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
                    m.SalesInvoice.posted_at >= start,
                    m.SalesInvoice.posted_at <= end,
                )
            )
        ).scalar()
        or 0
    )
    pos = float(
        (
            await db.execute(
                select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
                    m.Transaction.tenant_id == tenant_id,
                    m.Transaction.tx_type == "pos_sale",
                    m.Transaction.created_at >= start,
                    m.Transaction.created_at <= end,
                )
            )
        ).scalar()
        or 0
    )
    return round(inv + pos, 2)


async def sales_by_product(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    stmt = select(m.SalesInvoiceItem, m.SalesInvoice, m.Product).join(
        m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id
    ).join(m.Product, m.Product.id == m.SalesInvoiceItem.product_id).where(
        m.SalesInvoiceItem.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
    )
    if from_date:
        stmt = stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        stmt = stmt.where(m.SalesInvoice.posted_at <= to_date)
    rows = (await db.execute(stmt)).all()

    agg: dict[str, dict] = {}
    for item, _inv, product in rows:
        row = agg.setdefault(
            product.id,
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": 0.0,
                "revenue": 0.0,
            },
        )
        row["quantity"] = round(row["quantity"] + float(item.quantity or 0), 3)
        row["revenue"] = round(row["revenue"] + float(item.line_total or 0), 2)

    # Include POS payload items where possible
    pos_stmt = select(m.Transaction).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
    )
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    for tx in (await db.execute(pos_stmt)).scalars().all():
        for line in (tx.payload or {}).get("items") or []:
            pid = line.get("product_id")
            if not pid:
                continue
            product = await db.get(m.Product, pid)
            if not product or product.tenant_id != tenant_id:
                continue
            row = agg.setdefault(
                product.id,
                {
                    "product_id": product.id,
                    "sku": product.sku,
                    "name": product.name,
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
        "products": products,
        "total_revenue": round(sum(p["revenue"] for p in products), 2),
        "total_quantity": round(sum(p["quantity"] for p in products), 3),
    }


async def sales_by_salesperson(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
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
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
    )
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


async def inventory_balance(db: AsyncSession, tenant_id: str, warehouse_id: str | None = None) -> dict:
    if warehouse_id:
        rows = (
            await db.execute(
                select(m.WarehouseStock, m.Product)
                .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
                .where(
                    m.WarehouseStock.tenant_id == tenant_id,
                    m.WarehouseStock.warehouse_id == warehouse_id,
                )
                .order_by(m.Product.name)
            )
        ).all()
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
        "items": items,
        "total_quantity": round(sum(i["quantity"] for i in items), 3),
        "total_value": round(sum(i["value"] for i in items), 2),
    }


async def inventory_movements(
    db: AsyncSession,
    tenant_id: str,
    *,
    product_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 200,
) -> dict:
    stmt = select(m.StockMovement).where(m.StockMovement.tenant_id == tenant_id)
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
) -> dict:
    """Product-level and optional store/warehouse reorder breaches."""
    from app.inventory import compute_stock_status

    products = (
        await db.execute(
            select(m.Product).where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active == True,  # noqa: E712
            ).order_by(m.Product.stock_qty.asc())
        )
    ).scalars().all()
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
) -> dict:
    from app import catalog as catalog_svc

    batches = await catalog_svc.list_expiring_batches(
        db, tenant_id, within_days=within_days
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
) -> dict:
    stmt = select(m.PurchaseOrder).where(
        m.PurchaseOrder.tenant_id == tenant_id,
        m.PurchaseOrder.status != "cancelled",
    )
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
) -> dict:
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


async def expenses_summary(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    category_id: str | None = None,
) -> dict:
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


async def cash_flow(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    """Cash flow from cash + bank GL accounts (is_cash_account / is_bank_account)."""
    from app.accounting import ensure_default_accounts

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
        return {"inflows": 0, "outflows": 0, "net": 0, "lines": [], "accounts": []}

    account_ids = [a.id for a in liquid]
    by_id = {a.id: a for a in liquid}
    stmt = (
        select(m.JournalEntryLine, m.JournalEntry)
        .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntryLine.account_id.in_(account_ids),
        )
    )
    if from_date:
        stmt = stmt.where(m.JournalEntry.entry_date >= from_date)
    if to_date:
        stmt = stmt.where(m.JournalEntry.entry_date <= to_date)
    rows = (await db.execute(stmt.order_by(m.JournalEntry.entry_date.asc()))).all()
    inflows = 0.0
    outflows = 0.0
    lines = []
    for line, entry in rows:
        debit = float(line.debit or 0)
        credit = float(line.credit or 0)
        inflows += debit
        outflows += credit
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
            }
        )
    return {
        "inflows": round(inflows, 2),
        "outflows": round(outflows, 2),
        "net": round(inflows - outflows, 2),
        "lines": lines,
        "accounts": [{"id": a.id, "code": a.code, "name": a.name} for a in liquid],
    }


async def balance_sheet(db: AsyncSession, tenant_id: str) -> dict:
    """Point-in-time balance sheet from account balances."""
    accounts = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id).order_by(m.Account.code)
        )
    ).scalars().all()

    def rows_for(account_type: str) -> list[dict]:
        return [
            {
                "code": a.code,
                "name": a.name,
                "balance": round(float(a.balance or 0), 2),
            }
            for a in accounts
            if a.account_type == account_type
        ]

    assets = rows_for("asset")
    liabilities = rows_for("liability")
    equity = rows_for("equity")
    # Retained earnings proxy from income - expense (not posted to equity yet)
    income = sum(float(a.balance or 0) for a in accounts if a.account_type == "income")
    expense = sum(float(a.balance or 0) for a in accounts if a.account_type == "expense")
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
        "as_of": datetime.utcnow().date().isoformat(),
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_liabilities_and_equity": round(total_liabilities + total_equity, 2),
        "balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.01,
    }
