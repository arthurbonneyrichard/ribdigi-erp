"""Store-scoped dashboard resolution for Store Managers (Stage 81 S1 / ADR-005 adjacency).

Also used for operational list/read hardening (POS sales, sales invoices, expenses,
transfers, warehouses / inventory movements) and accounting statement reads
(P&L / TB / cash-flow / balance-sheet) and bank recon unmatched book lines — still
``stores.manager_id`` only;
ADR-005 membership tables remain deferred. Warehouse scope maps via
``Warehouse.store_id`` ∈ managed stores. POS holds scope via
``PosSession.store_id``; drawer-settings export uses managed store IDs.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.dashboard_views import dashboard_view_for_role


async def managed_store_ids(db: AsyncSession, claims: dict) -> list[str] | None:
    """Return managed store IDs for store_manager view; None means tenant-wide (no store filter).

    Uses ``stores.manager_id`` only (ADR-005 — no user↔store membership table).
    """
    role = (claims.get("role") or "").strip().lower()
    if dashboard_view_for_role(role) != "store_manager":
        return None
    user_id = claims.get("sub")
    tenant_id = claims.get("tenant_id")
    if not user_id or not tenant_id:
        return []
    rows = (
        await db.execute(
            select(m.Store.id).where(
                m.Store.tenant_id == tenant_id,
                m.Store.manager_id == user_id,
                m.Store.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    return [str(sid) for sid in rows]


def store_scope_payload(store_ids: list[str] | None) -> dict:
    if store_ids is None:
        return {"mode": "tenant", "store_ids": [], "managed_store_count": None}
    return {
        "mode": "managed_stores",
        "store_ids": list(store_ids),
        "managed_store_count": len(store_ids),
    }


def assert_store_in_manager_scope(
    managed_ids: list[str] | None,
    store_id: str | None,
    *,
    allow_unset: bool = True,
) -> None:
    """403 when a store_manager requests a store outside ``manager_id`` scope.

    When ``allow_unset`` is False, missing ``store_id`` is also denied (fail closed
    for records that should be store-bound for managers).
    """
    if managed_ids is None:
        return
    sid = (store_id or "").strip()
    if not sid:
        if allow_unset:
            return
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Record has no store assignment within your managed store scope.",
                "store_id": None,
            },
        )
    if sid not in managed_ids:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Store is outside your managed store scope.",
                "store_id": sid,
            },
        )


async def assert_pos_session_store_in_manager_scope(
    db: AsyncSession,
    claims: dict,
    session_id: str | None,
    *,
    require_session: bool = False,
) -> None:
    """403 when a store_manager references a POS session outside managed stores.

    Held carts have no ``store_id``; scope follows ``PosSession.store_id``.
    When ``require_session`` is True, missing ``session_id`` is denied.
    """
    managed = await managed_store_ids(db, claims)
    if managed is None:
        return
    sid = (session_id or "").strip() or None
    if not sid:
        assert_store_in_manager_scope(managed, None, allow_unset=not require_session)
        return
    session = await db.get(m.PosSession, sid)
    if not session or session.tenant_id != claims.get("tenant_id"):
        raise HTTPException(status_code=404, detail="POS session not found")
    company_id = claims.get("company_id")
    if company_id and session.company_id and session.company_id != company_id:
        raise HTTPException(status_code=404, detail="POS session not found")
    assert_store_in_manager_scope(
        managed, getattr(session, "store_id", None), allow_unset=False
    )


async def assert_journal_line_in_manager_scope(
    db: AsyncSession,
    tenant_id: str,
    journal_line_id: str,
    managed_ids: list[str] | None,
) -> None:
    """403 when a store_manager references a journal line outside managed stores."""
    if managed_ids is None:
        return
    jid = (journal_line_id or "").strip()
    if not jid:
        raise HTTPException(status_code=400, detail="journal_line_id required")
    row = (
        await db.execute(
            select(m.JournalEntryLine, m.JournalEntry)
            .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
            .where(
                m.JournalEntryLine.id == jid,
                m.JournalEntryLine.tenant_id == tenant_id,
            )
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Journal line not found")
    _line, entry = row
    assert_store_in_manager_scope(
        managed_ids, getattr(entry, "store_id", None), allow_unset=False
    )


def assert_transfer_touches_manager_scope(
    managed_ids: list[str] | None,
    *,
    from_store_id: str | None,
    to_store_id: str | None,
) -> None:
    """403 unless transfer involves at least one managed store (store_manager)."""
    if managed_ids is None:
        return
    touched = {
        sid
        for sid in ((from_store_id or "").strip(), (to_store_id or "").strip())
        if sid
    }
    if not touched or touched.isdisjoint(set(managed_ids)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Stock transfer is outside your managed store scope.",
                "from_store_id": from_store_id,
                "to_store_id": to_store_id,
            },
        )


def constrain_store_query(
    managed_ids: list[str] | None,
    requested_store_id: str | None = None,
) -> tuple[str | None, list[str] | None]:
    """Resolve list filters for store_manager.

    Returns ``(single_store_id, store_ids_in)``:
    - tenant-wide roles: ``(requested, None)``
    - store_manager with request: validates then ``(requested, None)``
    - store_manager without request: ``(None, managed_ids)`` (may be empty)
    """
    req = (requested_store_id or "").strip() or None
    if managed_ids is None:
        return req, None
    if req:
        assert_store_in_manager_scope(managed_ids, req)
        return req, None
    return None, list(managed_ids)


async def managed_warehouse_ids(db: AsyncSession, claims: dict) -> list[str] | None:
    """Warehouse IDs linked to managed stores; None = tenant-wide; [] = none.

    Warehouses with null ``store_id`` (central / unassigned) are out of store_manager
    scope. Still ``stores.manager_id`` only — ADR-005 deferred.
    """
    managed_stores = await managed_store_ids(db, claims)
    if managed_stores is None:
        return None
    if not managed_stores:
        return []
    stmt = select(m.Warehouse.id).where(
        m.Warehouse.tenant_id == claims["tenant_id"],
        m.Warehouse.store_id.in_(managed_stores),
    )
    company_id = claims.get("company_id")
    if company_id:
        stmt = stmt.where(m.Warehouse.company_id == company_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [str(wid) for wid in rows]


def assert_warehouse_in_manager_scope(
    managed_wh_ids: list[str] | None,
    warehouse_id: str | None,
    *,
    allow_unset: bool = True,
) -> None:
    """403 when a store_manager targets a warehouse outside managed-store WHs."""
    if managed_wh_ids is None:
        return
    wid = (warehouse_id or "").strip()
    if not wid:
        if allow_unset:
            return
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Warehouse is required within your managed store scope.",
                "warehouse_id": None,
            },
        )
    if wid not in managed_wh_ids:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Warehouse is outside your managed store scope.",
                "warehouse_id": wid,
            },
        )


def constrain_warehouse_query(
    managed_wh_ids: list[str] | None,
    requested_warehouse_id: str | None = None,
) -> tuple[str | None, list[str] | None]:
    """Resolve warehouse list filters for store_manager (mirrors constrain_store_query)."""
    req = (requested_warehouse_id or "").strip() or None
    if managed_wh_ids is None:
        return req, None
    if req:
        assert_warehouse_in_manager_scope(managed_wh_ids, req)
        return req, None
    return None, list(managed_wh_ids)


def apply_warehouse_scope_filter(stmt, model, managed_wh_ids: list[str] | None):
    """Restrict rows to managed warehouses; null warehouse_id excluded for managers."""
    if managed_wh_ids is None:
        return stmt
    if not managed_wh_ids:
        return stmt.where(func.false())
    return stmt.where(getattr(model, "warehouse_id").in_(managed_wh_ids))


def apply_sales_return_store_scope(stmt, store_ids: list[str] | None):
    """Scope sales returns via linked ``SalesInvoice.store_id`` (null-store fail-closed)."""
    if store_ids is None:
        return stmt
    stmt = stmt.join(
        m.SalesInvoice, m.SalesInvoice.id == m.SalesReturn.sales_invoice_id
    )
    if not store_ids:
        return stmt.where(m.SalesInvoice.id.is_(None))  # empty managed → no rows
    return stmt.where(m.SalesInvoice.store_id.in_(store_ids))


def apply_quotation_store_scope(
    stmt,
    *,
    managed_store_ids: list[str] | None,
    user_id: str | None,
    tenant_id: str,
    company_id: str | None = None,
):
    """Scope quotations without ``store_id``: own drafts + converted in-scope docs.

    Open/unconverted foreign quotes are fail-closed (no store column; ADR-005 deferred).
    """
    if managed_store_ids is None:
        return stmt
    if not managed_store_ids:
        if user_id:
            return stmt.where(m.SalesQuotation.created_by == user_id)
        return stmt.where(m.SalesQuotation.id.is_(None))

    in_scope_order = select(m.SalesOrder.id).where(
        m.SalesOrder.tenant_id == tenant_id,
        m.SalesOrder.store_id.in_(managed_store_ids),
    )
    in_scope_inv = select(m.SalesInvoice.id).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.store_id.in_(managed_store_ids),
    )
    if company_id:
        in_scope_order = in_scope_order.where(m.SalesOrder.company_id == company_id)
        in_scope_inv = in_scope_inv.where(m.SalesInvoice.company_id == company_id)

    visible = or_(
        m.SalesQuotation.converted_order_id.in_(in_scope_order),
        m.SalesQuotation.converted_invoice_id.in_(in_scope_inv),
    )
    if user_id:
        visible = or_(visible, m.SalesQuotation.created_by == user_id)
    return stmt.where(visible)


async def assert_quotation_in_manager_scope(
    db: AsyncSession, claims: dict, quote: m.SalesQuotation
) -> None:
    """403 when quotation is outside managed store scope (via conversion or own draft)."""
    managed = await managed_store_ids(db, claims)
    if managed is None:
        return
    user_id = claims.get("sub")
    if user_id and quote.created_by == user_id:
        return
    if not managed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "STORE_SCOPE_DENIED",
                "message": "Quotation is outside your managed store scope.",
            },
        )
    if quote.converted_order_id:
        order = await db.get(m.SalesOrder, quote.converted_order_id)
        sid = getattr(order, "store_id", None) if order else None
        if sid and str(sid) in managed:
            return
    if quote.converted_invoice_id:
        inv = await db.get(m.SalesInvoice, quote.converted_invoice_id)
        sid = getattr(inv, "store_id", None) if inv else None
        if sid and str(sid) in managed:
            return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "STORE_SCOPE_DENIED",
            "message": "Quotation is outside your managed store scope.",
        },
    )


async def assert_sales_return_in_manager_scope(
    db: AsyncSession, claims: dict, sales_return: m.SalesReturn
) -> None:
    """403 when return's invoice store is outside managed scope."""
    managed = await managed_store_ids(db, claims)
    if managed is None:
        return
    inv = await db.get(m.SalesInvoice, sales_return.sales_invoice_id)
    sid = getattr(inv, "store_id", None) if inv else None
    assert_store_in_manager_scope(managed, sid, allow_unset=False)


def apply_purchase_invoice_warehouse_scope(stmt, managed_wh_ids: list[str] | None):
    """Scope purchase invoices via direct warehouse_id, else linked GRN/PO warehouse.

    Prefer ``PurchaseInvoice.warehouse_id``, then GRN, then PO. Unlinked invoices with
    null warehouse remain fail-closed for store_managers.
    """
    if managed_wh_ids is None:
        return stmt
    if not managed_wh_ids:
        return stmt.where(func.false())
    stmt = stmt.outerjoin(
        m.GoodsReceipt, m.GoodsReceipt.id == m.PurchaseInvoice.goods_receipt_id
    ).outerjoin(
        m.PurchaseOrder, m.PurchaseOrder.id == m.PurchaseInvoice.purchase_order_id
    )
    wh_expr = func.coalesce(
        m.PurchaseInvoice.warehouse_id,
        m.GoodsReceipt.warehouse_id,
        m.PurchaseOrder.warehouse_id,
    )
    return stmt.where(wh_expr.in_(managed_wh_ids))


async def resolve_purchase_invoice_warehouse_id(
    db: AsyncSession, inv: m.PurchaseInvoice
) -> str | None:
    """Prefer direct PI.warehouse_id, then GRN, then PO."""
    direct = getattr(inv, "warehouse_id", None)
    if direct:
        return str(direct)
    if getattr(inv, "goods_receipt_id", None):
        grn = await db.get(m.GoodsReceipt, inv.goods_receipt_id)
        if grn and getattr(grn, "warehouse_id", None):
            return str(grn.warehouse_id)
    if getattr(inv, "purchase_order_id", None):
        po = await db.get(m.PurchaseOrder, inv.purchase_order_id)
        if po and getattr(po, "warehouse_id", None):
            return str(po.warehouse_id)
    return None


async def assert_purchase_invoice_in_manager_scope(
    db: AsyncSession, claims: dict, inv: m.PurchaseInvoice
) -> None:
    managed_wh = await managed_warehouse_ids(db, claims)
    if managed_wh is None:
        return
    wid = await resolve_purchase_invoice_warehouse_id(db, inv)
    assert_warehouse_in_manager_scope(managed_wh, wid, allow_unset=False)


async def assert_purchase_invoice_links_in_manager_scope(
    db: AsyncSession,
    claims: dict,
    *,
    goods_receipt_id: str | None,
    purchase_order_id: str | None,
    warehouse_id: str | None = None,
) -> None:
    """Create-time gate: managers need a managed warehouse (explicit or via GRN/PO)."""
    managed_wh = await managed_warehouse_ids(db, claims)
    if managed_wh is None:
        return
    wid = (warehouse_id or "").strip() or None
    if not wid and goods_receipt_id:
        grn = await db.get(m.GoodsReceipt, goods_receipt_id)
        if grn and getattr(grn, "warehouse_id", None):
            wid = str(grn.warehouse_id)
    if not wid and purchase_order_id:
        po = await db.get(m.PurchaseOrder, purchase_order_id)
        if po and getattr(po, "warehouse_id", None):
            wid = str(po.warehouse_id)
    assert_warehouse_in_manager_scope(managed_wh, wid, allow_unset=False)


async def scoped_financial_kpis(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_ids: list[str],
    day_start: datetime,
    yesterday_start: datetime,
    month_start: datetime,
    prior_month_start: datetime,
) -> dict:
    """Sales / expense KPIs limited to managed stores. Purchase invoices use PO/GRN WH join elsewhere."""

    async def scalar(stmt):
        return (await db.execute(stmt)).scalar() or 0

    if not store_ids:
        return {
            "total_sales": 0.0,
            "total_purchases": 0.0,
            "total_expenses": 0.0,
            "daily_revenue": 0.0,
            "yesterday_revenue": 0.0,
            "monthly_revenue": 0.0,
            "prior_month_revenue": 0.0,
            "dod_change_pct": None,
            "mom_change_pct": None,
            "recent_sales": [],
            "top_products": [],
        }

    inv_posted = m.SalesInvoice.status.in_(["posted", "partial", "paid"])
    inv_store = m.SalesInvoice.store_id.in_(store_ids)

    inv_total = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id, inv_posted, inv_store
            )
        )
    )
    inv_daily = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
                m.SalesInvoice.posted_at >= day_start,
            )
        )
    )
    inv_yesterday = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
                m.SalesInvoice.posted_at >= yesterday_start,
                m.SalesInvoice.posted_at < day_start,
            )
        )
    )
    inv_monthly = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
                m.SalesInvoice.posted_at >= month_start,
            )
        )
    )
    inv_prior = float(
        await scalar(
            select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
                m.SalesInvoice.posted_at >= prior_month_start,
                m.SalesInvoice.posted_at < month_start,
            )
        )
    )

    # POS txs attributed via PosSession.store_id
    async def pos_sum(*extra):
        stmt = (
            select(func.coalesce(func.sum(m.Transaction.total), 0))
            .select_from(m.Transaction)
            .join(m.PosSession, m.Transaction.session_id == m.PosSession.id)
            .where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type.in_(["sale", "pos_sale"]),
                m.PosSession.store_id.in_(store_ids),
                *extra,
            )
        )
        return float(await scalar(stmt))

    pos_total = await pos_sum()
    pos_daily = await pos_sum(m.Transaction.created_at >= day_start)
    pos_yesterday = await pos_sum(
        m.Transaction.created_at >= yesterday_start,
        m.Transaction.created_at < day_start,
    )
    pos_monthly = await pos_sum(m.Transaction.created_at >= month_start)
    pos_prior = await pos_sum(
        m.Transaction.created_at >= prior_month_start,
        m.Transaction.created_at < month_start,
    )

    expenses = float(
        await scalar(
            select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
                m.Expense.tenant_id == tenant_id,
                m.Expense.status == "approved",
                m.Expense.store_id.in_(store_ids),
            )
        )
    )

    daily_revenue = pos_daily + inv_daily
    yesterday_revenue = pos_yesterday + inv_yesterday
    monthly_revenue = pos_monthly + inv_monthly
    prior_month_revenue = pos_prior + inv_prior
    dod_change_pct = None
    if yesterday_revenue > 0:
        dod_change_pct = round(((daily_revenue - yesterday_revenue) / yesterday_revenue) * 100, 2)
    mom_change_pct = None
    if prior_month_revenue > 0:
        mom_change_pct = round(
            ((monthly_revenue - prior_month_revenue) / prior_month_revenue) * 100, 2
        )

    recent_invoices = (
        await db.execute(
            select(m.SalesInvoice)
            .where(
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
            )
            .order_by(m.SalesInvoice.posted_at.desc())
            .limit(10)
        )
    ).scalars().all()
    recent = [
        {
            "source": "invoice",
            "reference": inv.invoice_number,
            "total": float(inv.total_amount or 0),
            "at": inv.posted_at or inv.created_at,
            "store_id": inv.store_id,
        }
        for inv in recent_invoices
    ]

    top_rows = (
        await db.execute(
            select(
                m.Product.id,
                m.Product.name,
                m.Product.sku,
                func.coalesce(func.sum(m.SalesInvoiceItem.quantity), 0).label("qty"),
                func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).label("revenue"),
            )
            .join(m.SalesInvoiceItem, m.SalesInvoiceItem.product_id == m.Product.id)
            .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesInvoiceItem.sales_invoice_id)
            .where(
                m.Product.tenant_id == tenant_id,
                m.SalesInvoice.tenant_id == tenant_id,
                inv_posted,
                inv_store,
            )
            .group_by(m.Product.id, m.Product.name, m.Product.sku)
            .order_by(func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).desc())
            .limit(5)
        )
    ).all()
    top_products = [
        {
            "id": row.id,
            "name": row.name,
            "sku": row.sku,
            "quantity": float(row.qty or 0),
            "revenue": float(row.revenue or 0),
        }
        for row in top_rows
    ]

    return {
        "total_sales": pos_total + inv_total,
        "total_purchases": 0.0,  # PurchaseInvoice has no store_id — do not leak tenant-wide
        "total_expenses": expenses,
        "daily_revenue": daily_revenue,
        "yesterday_revenue": yesterday_revenue,
        "monthly_revenue": monthly_revenue,
        "prior_month_revenue": prior_month_revenue,
        "dod_change_pct": dod_change_pct,
        "mom_change_pct": mom_change_pct,
        "recent_sales": recent,
        "top_products": top_products,
    }
