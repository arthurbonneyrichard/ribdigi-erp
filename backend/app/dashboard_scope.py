"""Store-scoped dashboard resolution for Store Managers (Stage 81 S1 / ADR-005 adjacency)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, func
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
    """Sales / expense KPIs limited to managed stores. Purchases omitted (no store axis on PI)."""

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
