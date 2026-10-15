"""Executive dashboard aggregates (BR-4.1 / 4.2 / 4.3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import tenants as tenants_svc
from app.config import settings
from app.honesty import money_json


def _pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None if current == 0 else money_json(100)
    return money_json(round((current - previous) / abs(previous) * 100.0, 1))


def _day_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def _month_start(year: int, month: int) -> datetime:
    return datetime(year, month, 1)


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1


# Supplier bills that have left draft. The headline is to-date recorded purchases,
# not this month and not open purchase orders. Paid stays in the total.
RECORDED_PURCHASE_INVOICE_STATUSES = ("unpaid", "partial", "paid", "overdue")


def _tx_store_scope(stmt, store_id: str | None, store_ids: list[str] | None):
    """Limit sale rows to one store or the caller's assigned stores."""
    if not store_id and store_ids is None:
        return stmt
    from app.reports import apply_store_scope

    stmt = stmt.outerjoin(m.PosSession, m.Transaction.session_id == m.PosSession.id)
    return apply_store_scope(stmt, m.PosSession.store_id, store_id, store_ids)


async def _sum_sales(
    db: AsyncSession,
    tenant_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> float:
    stmt = select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type.in_(["sale", "pos_sale"]),
    )
    stmt = _tx_store_scope(stmt, store_id, store_ids)
    if start is not None:
        stmt = stmt.where(m.Transaction.created_at >= start)
    if end is not None:
        stmt = stmt.where(m.Transaction.created_at < end)
    return money_json((await db.execute(stmt)).scalar())


async def build_dashboard(
    db: AsyncSession,
    tenant_id: str,
    *,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> dict[str, Any]:
    from fastapi import HTTPException

    from app.industry_dashboard import industry_dashboard_payload, is_software_owner_industry

    tenant = await db.get(m.Tenant, tenant_id)
    if tenant and is_software_owner_industry(getattr(tenant, "industry", None)):
        # Software-owner home is the platform console. Do not attach a customer operating desk.
        return {
            **industry_dashboard_payload(tenant),
            "scope": "platform",
            "pharmacy_desk": None,
            "fmcg_desk": None,
            "hospital_desk": None,
            "wholesale_desk": None,
            "recent_sales": [],
            "monthly_sales": [],
            "daily_sales": [],
            "top_products_by_revenue": [],
            "top_products_by_quantity": [],
            "links": {
                "platform": "/platform",
                "tenants": "/platform/tenants",
                "reports": "/platform/reports",
                "support": "/platform/support",
            },
        }

    async def scalar(stmt):
        return (await db.execute(stmt)).scalar() or 0

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

    now_dt = datetime.utcnow()
    today = now_dt.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    this_month = _month_start(today.year, today.month)
    prev_y, prev_m = _add_months(today.year, today.month, -1)
    prev_month = _month_start(prev_y, prev_m)

    sales_all = await _sum_sales(db, tenant_id, store_id=store_id, store_ids=store_ids)
    sales_today = await _sum_sales(
        db, tenant_id, start=_day_start(today), end=_day_start(tomorrow), store_id=store_id, store_ids=store_ids
    )
    sales_yesterday = await _sum_sales(
        db, tenant_id, start=_day_start(yesterday), end=_day_start(today), store_id=store_id, store_ids=store_ids
    )
    sales_mtd = await _sum_sales(
        db, tenant_id, start=this_month, end=_day_start(tomorrow), store_id=store_id, store_ids=store_ids
    )
    sales_prev_month = await _sum_sales(
        db, tenant_id, start=prev_month, end=this_month, store_id=store_id, store_ids=store_ids
    )

    # Legacy POST /purchases rows. The purchasing screens write purchase invoices
    # instead, so those bills are added below and are not in this sum.
    purchases_stmt = select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "purchase",
    )
    purchases_stmt = _tx_store_scope(purchases_stmt, store_id, store_ids)
    legacy_purchases = money_json(await scalar(purchases_stmt))
    expenses_stmt = select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
        m.Expense.tenant_id == tenant_id,
        m.Expense.status == "approved",
    )
    from app.reports import apply_store_scope

    expenses_stmt = apply_store_scope(expenses_stmt, m.Expense.store_id, store_id, store_ids)
    expenses = money_json(await scalar(expenses_stmt))
    # Never SELECT the full Product mapper row — live DBs can omit later catalog
    # columns while still having extra company_id.
    from app import schema_compat
    from app.catalog_meta import qty_is_low_stock, qty_is_out_of_stock

    invoice_purchases = 0.0
    if await schema_compat.table_column_names(db, "purchase_invoices"):
        invoice_stmt = select(func.coalesce(func.sum(m.PurchaseInvoice.total_amount), 0)).where(
            m.PurchaseInvoice.tenant_id == tenant_id,
            m.PurchaseInvoice.status.in_(RECORDED_PURCHASE_INVOICE_STATUSES),
        )
        invoice_stmt = apply_store_scope(
            invoice_stmt, m.PurchaseInvoice.store_id, store_id, store_ids
        )
        invoice_purchases = money_json(await scalar(invoice_stmt))
    # Purchase orders are not added: a billed order is already on its invoice.
    purchases = money_json(round(legacy_purchases + invoice_purchases, 2))

    live_product_cols = await schema_compat.table_column_names(db, "products")
    stock_col_names = (
        "id",
        "stock_qty",
        "is_active",
        "reorder_level",
        "minimum_stock",
    )
    stock_cols = [
        getattr(m.Product, name)
        for name in stock_col_names
        if name in live_product_cols and hasattr(m.Product, name)
    ]
    product_rows = (
        await db.execute(select(*stock_cols).where(m.Product.tenant_id == tenant_id))
    ).all()
    qty_by_product: dict[str, float] | None = None
    if store_id or store_ids is not None:
        wh_stmt = select(m.Warehouse.id).where(m.Warehouse.tenant_id == tenant_id)
        if store_id:
            wh_stmt = wh_stmt.where(m.Warehouse.store_id == store_id)
        elif store_ids:
            wh_stmt = wh_stmt.where(m.Warehouse.store_id.in_(list(store_ids)))
        else:
            wh_stmt = wh_stmt.where(m.Warehouse.id.is_(None))
        wh_ids = list((await db.execute(wh_stmt)).scalars().all())
        qty_by_product = {row._mapping["id"]: 0.0 for row in product_rows}
        if wh_ids:
            sums = (
                await db.execute(
                    select(m.WarehouseStock.product_id, func.sum(m.WarehouseStock.quantity))
                    .where(
                        m.WarehouseStock.tenant_id == tenant_id,
                        m.WarehouseStock.warehouse_id.in_(wh_ids),
                    )
                    .group_by(m.WarehouseStock.product_id)
                )
            ).all()
            for pid, qty in sums:
                qty_by_product[pid] = qty or 0
    products = len(product_rows)
    out_of_stock = 0
    low_stock = 0
    for row in product_rows:
        data = row._mapping
        if not data.get("is_active", True):
            continue
        qty = (
            qty_by_product.get(data["id"], 0)
            if qty_by_product is not None
            else data.get("stock_qty") or 0
        )
        if qty_is_out_of_stock(qty):
            out_of_stock += 1
        elif qty_is_low_stock(
            qty,
            minimum_stock=data.get("minimum_stock") or 0,
            reorder_level=data.get("reorder_level") or 0,
        ):
            low_stock += 1
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
    from app import credit as credit_svc

    expiring_batches = await list_expiring_batches(db, tenant_id, within_days=30)
    expiring_soon = len(expiring_batches)

    # Tenant-scoped AR/AP from the same aging engine as /credit/aging (not store-invented).
    ar_aging = await credit_svc.ar_aging(db, tenant_id)
    ap_aging = await credit_svc.ap_aging(db, tenant_id)
    ar_total_due = money_json(ar_aging.get("total_due") or 0)
    ap_total_due = money_json(ap_aging.get("total_due") or 0)
    credit_outstanding = money_json(round(float(ar_total_due) + float(ap_total_due), 2))
    ar_open_parties = sum(
        1 for p in (ar_aging.get("parties") or []) if money_json(p.get("total_due") or 0) > 0
    )
    ap_open_parties = sum(
        1 for p in (ap_aging.get("parties") or []) if money_json(p.get("total_due") or 0) > 0
    )

    # Monthly sales trend (last 12 calendar months)
    months_seq = []
    for i in range(11, -1, -1):
        yy, mm = _add_months(now_dt.year, now_dt.month, -i)
        months_seq.append((yy, mm))
    earliest_month = _month_start(months_seq[0][0], months_seq[0][1])
    month_totals = {k: 0.0 for k in months_seq}
    trend_stmt = select(m.Transaction.created_at, m.Transaction.total).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type.in_(["sale", "pos_sale"]),
        m.Transaction.created_at >= earliest_month,
    )
    trend_stmt = _tx_store_scope(trend_stmt, store_id, store_ids)
    trend_rows = (await db.execute(trend_stmt)).all()
    for created_at, total in trend_rows:
        if created_at is None:
            continue
        key = (created_at.year, created_at.month)
        if key in month_totals:
            month_totals[key] += money_json(total or 0)
    monthly_sales = [
        {
            "label": datetime(yy, mm, 1).strftime("%b %y"),
            "year": yy,
            "month": mm,
            "total": money_json(round(month_totals[(yy, mm)], 2)),
        }
        for (yy, mm) in months_seq
    ]

    # Daily sales & profit for the last 30 days
    days_seq = [today - timedelta(days=i) for i in range(29, -1, -1)]
    earliest_day = _day_start(days_seq[0])
    cost_rows = (
        await db.execute(select(m.Product.id, m.Product.cost_price).where(m.Product.tenant_id == tenant_id))
    ).all()
    cost_map = {pid: money_json(cost or 0) for pid, cost in cost_rows}
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
    daily_stmt = select(
        m.Transaction.created_at, m.Transaction.total, m.Transaction.payload
    ).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type.in_(["sale", "pos_sale"]),
        m.Transaction.created_at >= earliest_day,
    )
    daily_stmt = _tx_store_scope(daily_stmt, store_id, store_ids)
    daily_rows = (await db.execute(daily_stmt)).all()
    for created_at, total, payload in daily_rows:
        if created_at is None:
            continue
        d = created_at.date()
        if d in daily:
            daily[d]["sales"] += money_json(total or 0)
            for it in (payload or {}).get("items") or []:
                qty = money_json(it.get("quantity") or 0)
                unit_price = money_json(it.get("unit_price") or 0)
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
            "sales": money_json(round(daily[d]["sales"], 2)),
            "profit": money_json(round(daily[d]["profit"], 2)),
        }
        for d in days_seq
    ]
    gross_profit_7d = money_json(round(sum(row["profit"] for row in daily_sales[-7:]), 2))
    gross_profit_30d = money_json(round(sum(row["profit"] for row in daily_sales), 2))

    def _top(metric: dict[str, float], *, limit: int = 5) -> list[dict]:
        ranked = sorted(metric.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        return [
            {
                "product_id": pid,
                "name": product_names.get(pid) or pid,
                "sku": product_skus.get(pid),
                "quantity": money_json(round(top_qty.get(pid, 0.0), 2)),
                "revenue": money_json(round(top_rev.get(pid, 0.0), 2)),
            }
            for pid, _ in ranked
        ]

    top_products_by_revenue = _top(top_rev)
    top_products_by_quantity = _top(top_qty)

    recent_stmt = (
        select(m.Transaction)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type.in_(["sale", "pos_sale"]),
        )
        .order_by(m.Transaction.created_at.desc())
        .limit(10)
    )
    recent_stmt = _tx_store_scope(recent_stmt, store_id, store_ids)
    recent_rows = (await db.execute(recent_stmt)).scalars().all()
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
            "total": money_json(t.total),
            "customer": recent_party_names.get(t.party_id) or "Walk-in",
            "type": t.tx_type,
        }
        for t in recent_rows
    ]

    tenant = await db.get(m.Tenant, tenant_id)
    from app.industry_dashboard import industry_dashboard_payload

    industry_payload = industry_dashboard_payload(tenant)
    rx_queue = None
    rx_only_count = None
    if industry_payload.get("industry") == "pharmacy":
        from app import pharmacy as pharmacy_svc
        from app import schema_compat as schema_compat_svc

        if await schema_compat_svc.table_column_names(db, "prescriptions"):
            rx_queue = await pharmacy_svc.queue_counts(db, tenant_id)
        else:
            rx_queue = {key: 0 for key in pharmacy_svc.RX_STATUSES}
            rx_queue["open"] = 0
        if "rx_only" in live_product_cols:
            from sqlalchemy import text as sql_text

            rx_only_count = int(
                (
                    await db.execute(
                        sql_text(
                            "SELECT COUNT(*) FROM products WHERE tenant_id = :tid AND rx_only = :rx"
                        ),
                        {"tid": tenant_id, "rx": True},
                    )
                ).scalar()
                or 0
            )
        else:
            rx_only_count = 0

    pharmacy_desk = None
    if industry_payload.get("industry") == "pharmacy":
        from app import schema_compat as schema_compat_svc

        wh_ids: list[str] | None = None
        if store_id or store_ids is not None:
            wh_stmt = select(m.Warehouse.id).where(m.Warehouse.tenant_id == tenant_id)
            if store_id:
                wh_stmt = wh_stmt.where(m.Warehouse.store_id == store_id)
            elif not store_ids:
                wh_ids = []
            else:
                wh_stmt = wh_stmt.where(m.Warehouse.store_id.in_(store_ids))
            if wh_ids is None:
                wh_ids = list((await db.execute(wh_stmt)).scalars().all())

        def _limit_warehouses(stmt, column):
            if wh_ids is None:
                return stmt
            if not wh_ids:
                return stmt.where(column == "__none__")
            return stmt.where(column.in_(wh_ids))

        returns_today = 0
        if await schema_compat_svc.table_column_names(db, "sales_returns"):
            ret_stmt = select(func.count()).select_from(m.SalesReturn).where(
                m.SalesReturn.tenant_id == tenant_id,
                m.SalesReturn.status == "posted",
                m.SalesReturn.created_at >= _day_start(today),
                m.SalesReturn.created_at < _day_start(tomorrow),
            )
            if store_id or store_ids is not None:
                ret_stmt = ret_stmt.join(
                    m.SalesInvoice, m.SalesInvoice.id == m.SalesReturn.sales_invoice_id
                )
                ret_stmt = apply_store_scope(ret_stmt, m.SalesInvoice.store_id, store_id, store_ids)
            returns_today = int((await db.execute(ret_stmt)).scalar() or 0)

        expired_lots = 0
        nearing_lots = 0
        on_hand_lots = 0
        if await schema_compat_svc.table_column_names(db, "product_batches"):
            lot_stmt = select(func.count()).select_from(m.ProductBatch).where(
                m.ProductBatch.tenant_id == tenant_id,
                m.ProductBatch.quantity > 0,
            )
            on_hand_lots = int(
                (await db.execute(_limit_warehouses(lot_stmt, m.ProductBatch.warehouse_id))).scalar() or 0
            )
            exp_stmt = select(func.count()).select_from(m.ProductBatch).where(
                m.ProductBatch.tenant_id == tenant_id,
                m.ProductBatch.expiry_date.is_not(None),
                m.ProductBatch.expiry_date < now_dt,
                m.ProductBatch.quantity > 0,
            )
            expired_lots = int((await db.execute(_limit_warehouses(exp_stmt, m.ProductBatch.warehouse_id))).scalar() or 0)
            near_stmt = select(func.count()).select_from(m.ProductBatch).where(
                m.ProductBatch.tenant_id == tenant_id,
                m.ProductBatch.expiry_date.is_not(None),
                m.ProductBatch.expiry_date >= now_dt,
                m.ProductBatch.expiry_date <= now_dt + timedelta(days=30),
                m.ProductBatch.quantity > 0,
            )
            nearing_lots = int((await db.execute(_limit_warehouses(near_stmt, m.ProductBatch.warehouse_id))).scalar() or 0)

        quarantined = 0
        recalled = 0
        if await schema_compat_svc.table_column_names(db, "batch_holds"):
            hold_stmt = (
                select(m.BatchHold.hold_type, func.count())
                .where(m.BatchHold.tenant_id == tenant_id, m.BatchHold.status == "open")
                .group_by(m.BatchHold.hold_type)
            )
            if wh_ids is not None:
                hold_stmt = hold_stmt.join(m.ProductBatch, m.ProductBatch.id == m.BatchHold.batch_id)
                hold_stmt = _limit_warehouses(hold_stmt, m.ProductBatch.warehouse_id)
            for hold_type, n in (await db.execute(hold_stmt)).all():
                if hold_type == "recall":
                    recalled += int(n or 0)
                else:
                    quarantined += int(n or 0)

        pending_purchase_orders = 0
        if await schema_compat_svc.table_column_names(db, "purchase_orders"):
            po_stmt = select(func.count()).select_from(m.PurchaseOrder).where(
                m.PurchaseOrder.tenant_id == tenant_id,
                m.PurchaseOrder.status.in_(["draft", "sent", "partially_received"]),
            )
            pending_purchase_orders = int(
                (await db.execute(_limit_warehouses(po_stmt, m.PurchaseOrder.warehouse_id))).scalar() or 0
            )

        queue = rx_queue or {}
        pharmacy_desk = {
            "sales_today": money_json(sales_today),
            "returns_today": returns_today,
            "awaiting_review": int(queue.get("received") or 0) + int(queue.get("review") or 0),
            "ready_to_dispense": int(queue.get("approved") or 0),
            "partially_dispensed": int(queue.get("partially_dispensed") or 0),
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "expiring_soon": nearing_lots,
            "expired_lots": expired_lots,
            "on_hand_lots": on_hand_lots,
            "quarantined": quarantined,
            "recalled": recalled,
            "pending_purchase_orders": pending_purchase_orders,
            "rx_only_count": rx_only_count or 0,
        }

    open_quotes = 0
    open_orders = 0
    reserved_qty = 0.0
    if industry_payload.get("industry") in {"wholesale", "retail_wholesale"}:
        open_quotes = int(
            await scalar(
                select(func.count(m.SalesQuotation.id)).where(
                    m.SalesQuotation.tenant_id == tenant_id,
                    m.SalesQuotation.status.in_(["draft", "sent", "accepted"]),
                )
            )
        )
        open_orders = int(
            await scalar(
                select(func.count(m.SalesOrder.id)).where(
                    m.SalesOrder.tenant_id == tenant_id,
                    m.SalesOrder.status.in_(["draft", "confirmed", "processing", "shipped"]),
                )
            )
        )
        reserved_qty = money_json(
            await scalar(
                select(func.coalesce(func.sum(m.StockReservation.quantity), 0)).where(
                    m.StockReservation.tenant_id == tenant_id,
                    m.StockReservation.status == "active",
                )
            )
        )

    if tenant and tenant.status == "trial":
        days_remaining = tenants_svc.calendar_days_until(tenant.trial_ends_at)
    elif tenant and tenant.status == "grace":
        days_remaining = tenants_svc.calendar_days_until(tenant.grace_ends_at)
    else:
        days_remaining = None

    industry_code = industry_payload.get("industry")
    fmcg_desk = None
    hospital_desk = None
    wholesale_desk = None
    if industry_code == "fmcg":
        from app import fmcg as fmcg_svc
        from app import schema_compat as schema_compat_svc

        if await schema_compat_svc.table_column_names(db, "fmcg_routes"):
            fmcg_desk = await fmcg_svc.summary(db, tenant_id=tenant_id)
        else:
            fmcg_desk = {
                "schemes_active": 0,
                "routes_active": 0,
                "route_stops": 0,
                "customers_active": 0,
                "batches_expiring_30d": 0,
                "deliveries_pending": 0,
                "deliveries_completed": 0,
                "deliveries_failed": 0,
            }
    if industry_code == "hospital":
        from app import schema_compat as schema_compat_svc

        patients = 0
        open_visits = 0
        if await schema_compat_svc.table_column_names(db, "hospital_patients"):
            patients = int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(m.HospitalPatient)
                        .where(m.HospitalPatient.tenant_id == tenant_id)
                    )
                ).scalar()
                or 0
            )
        if await schema_compat_svc.table_column_names(db, "hospital_encounters"):
            open_visits = int(
                (
                    await db.execute(
                        select(func.count())
                        .select_from(m.HospitalEncounter)
                        .where(
                            m.HospitalEncounter.tenant_id == tenant_id,
                            m.HospitalEncounter.status == "open",
                        )
                    )
                ).scalar()
                or 0
            )
        hospital_desk = {"patients": patients, "open_visits": open_visits}
    if industry_code in {"wholesale", "retail_wholesale"}:
        wholesale_desk = {
            "open_quotes": open_quotes,
            "open_orders": open_orders,
            "reserved_qty": reserved_qty,
            "ar_total_due": ar_total_due,
        }

    returns_count = None
    if industry_code in {"retail", "retail_wholesale"}:
        returns_count = 0
        if await schema_compat.table_column_names(db, "sales_returns"):
            ret_all = select(func.count()).select_from(m.SalesReturn).where(
                m.SalesReturn.tenant_id == tenant_id,
                m.SalesReturn.status == "posted",
            )
            if store_id or store_ids is not None:
                ret_all = ret_all.join(
                    m.SalesInvoice, m.SalesInvoice.id == m.SalesReturn.sales_invoice_id
                )
                ret_all = apply_store_scope(ret_all, m.SalesInvoice.store_id, store_id, store_ids)
            returns_count = int((await db.execute(ret_all)).scalar() or 0)

    subscription = {
        "status": tenant.status if tenant else None,
        "trial_ends_at": tenant.trial_ends_at if tenant else None,
        "grace_ends_at": tenant.grace_ends_at if tenant else None,
        "days_remaining": days_remaining,
        "read_only": tenants_svc.is_read_only(tenant) if tenant else False,
        "trial_days": int(settings.TRIAL_DAYS),
    }

    return {
        "scope": "store" if store_id or store_ids is not None else "tenant",
        "store_id": store_id,
        "store_name": store_name,
        "total_sales": money_json(sales_all),
        "total_purchases": money_json(purchases),
        "total_expenses": money_json(expenses),
        "products": products,
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "expiring_soon": expiring_soon,
        "expiring_within_days": 30,
        "customers": customers,
        "suppliers": suppliers,
        "ar_total_due": ar_total_due,
        "ap_total_due": ap_total_due,
        "credit_outstanding": credit_outstanding,
        "ar_open_parties": ar_open_parties,
        "ap_open_parties": ap_open_parties,
        "comparisons": {
            "sales_today": money_json(round(money_json(sales_today), 2)),
            "sales_yesterday": money_json(round(money_json(sales_yesterday), 2)),
            "sales_today_pct": _pct_change(sales_today, sales_yesterday),
            "sales_mtd": money_json(round(money_json(sales_mtd), 2)),
            "sales_prev_month": money_json(round(money_json(sales_prev_month), 2)),
            "sales_mtd_pct": _pct_change(sales_mtd, sales_prev_month),
        },
        "monthly_sales": monthly_sales,
        "daily_sales": daily_sales,
        "gross_profit_7d": gross_profit_7d,
        "gross_profit_30d": gross_profit_30d,
        "rx_queue": rx_queue,
        "rx_only_count": rx_only_count,
        "pharmacy_desk": pharmacy_desk,
        "fmcg_desk": fmcg_desk,
        "hospital_desk": hospital_desk,
        "wholesale_desk": wholesale_desk,
        "open_quotes": open_quotes,
        "open_orders": open_orders,
        "reserved_qty": reserved_qty,
        "recent_sales": recent_sales,
        "top_products_by_revenue": top_products_by_revenue,
        "top_products_by_quantity": top_products_by_quantity,
        "returns_count": returns_count,
        "links": {
            "sales": "/sales",
            "purchases": "/purchasing",
            "expenses": "/expenses",
            "customers": "/customers",
            "suppliers": "/purchasing",
            "products": "/inventory",
            "low_stock": "/inventory?tab=lowstock",
            "out_of_stock": "/inventory?tab=products&stock=oos",
            "expiring": "/inventory?tab=expiry",
            "batches": "/inventory?tab=batches",
            "prescriptions": "/prescriptions",
            "credit": "/credit",
            "ar_total_due": "/credit?kind=receivable",
            "ap_total_due": "/credit?kind=payable",
            "reports_sales": "/reports",
        },
        "subscription": subscription,
        "generated_at": now_dt,
        **industry_payload,
    }
