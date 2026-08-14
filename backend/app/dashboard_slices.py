"""Tenant dashboard KPI/chart slices (Stage 82 C1) — permission-filtered subroute payloads."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import dashboard_charts as dashboard_charts_svc
from app import dashboard_views as dashboard_views_svc
from app.reports import apply_company_filter
from app.rbac import ROLE_LABELS, list_system_role_catalog


def _meta(claims: dict) -> dict:
    role = claims.get("role") or ""
    return {
        "role_label": ROLE_LABELS.get(role, role),
        "kpi_links": {},
    }


async def sales_trend(
    db: AsyncSession, claims: dict, *, company_id: str | None = None
) -> dict:
    from app import dashboard_scope as dashboard_scope_svc

    tid = claims["tenant_id"]
    managed_ids = await dashboard_scope_svc.managed_store_ids(db, claims)
    series = await dashboard_charts_svc.load_revenue_chart_series(
        db,
        tenant_id=tid,
        now=datetime.utcnow(),
        store_ids=managed_ids,
        company_id=company_id,
    )
    payload = {
        **_meta(claims),
        "daily_revenue_series": series["daily_revenue_series"],
        "monthly_revenue_series": series["monthly_revenue_series"],
        "store_scope": dashboard_scope_svc.store_scope_payload(managed_ids),
    }
    return dashboard_views_svc.filter_dashboard_payload(payload, claims)


async def top_products(
    db: AsyncSession, claims: dict, *, company_id: str | None = None
) -> dict:
    from app import dashboard_scope as dashboard_scope_svc

    tid = claims["tenant_id"]
    managed_ids = await dashboard_scope_svc.managed_store_ids(db, claims)
    filters = [
        m.Product.tenant_id == tid,
        m.SalesInvoice.tenant_id == tid,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
    ]
    if company_id:
        filters.append(m.Product.company_id == company_id)
        filters.append(m.SalesInvoice.company_id == company_id)
    if managed_ids is not None:
        if not managed_ids:
            payload = {
                **_meta(claims),
                "top_products": [],
                "store_scope": dashboard_scope_svc.store_scope_payload(managed_ids),
            }
            return dashboard_views_svc.filter_dashboard_payload(payload, claims)
        filters.append(m.SalesInvoice.store_id.in_(managed_ids))

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
            .where(*filters)
            .group_by(m.Product.id, m.Product.name, m.Product.sku)
            .order_by(func.coalesce(func.sum(m.SalesInvoiceItem.line_total), 0).desc())
            .limit(5)
        )
    ).all()
    products = [
        {
            "id": row.id,
            "name": row.name,
            "sku": row.sku,
            "quantity": float(row.qty or 0),
            "revenue": float(row.revenue or 0),
        }
        for row in top_rows
    ]
    payload = {
        **_meta(claims),
        "top_products": products,
        "store_scope": dashboard_scope_svc.store_scope_payload(managed_ids),
    }
    return dashboard_views_svc.filter_dashboard_payload(payload, claims)


async def stock_alerts(
    db: AsyncSession, claims: dict, *, company_id: str | None = None
) -> dict:
    tid = claims["tenant_id"]
    now = datetime.utcnow()
    from datetime import timedelta

    expiry_horizon = now + timedelta(days=30)

    async def scalar(stmt):
        return (await db.execute(stmt)).scalar() or 0

    low_stmt = select(func.count(m.Product.id)).where(
        m.Product.tenant_id == tid,
        m.Product.stock_qty <= m.Product.reorder_level,
    )
    low_stmt = apply_company_filter(low_stmt, m.Product.company_id, company_id)
    low = await scalar(low_stmt)

    oos_stmt = select(func.count(m.Product.id)).where(
        m.Product.tenant_id == tid,
        m.Product.stock_qty <= 0,
    )
    oos_stmt = apply_company_filter(oos_stmt, m.Product.company_id, company_id)
    out_of_stock = await scalar(oos_stmt)

    exp_stmt = select(func.count(m.ProductBatch.id)).where(
        m.ProductBatch.tenant_id == tid,
        m.ProductBatch.expiry_date.is_not(None),
        m.ProductBatch.expiry_date >= now,
        m.ProductBatch.expiry_date <= expiry_horizon,
        m.ProductBatch.quantity > 0,
    )
    exp_stmt = apply_company_filter(exp_stmt, m.ProductBatch.company_id, company_id)
    expiring_batches = await scalar(exp_stmt)

    products_stmt = select(func.count(m.Product.id)).where(m.Product.tenant_id == tid)
    products_stmt = apply_company_filter(products_stmt, m.Product.company_id, company_id)
    products = await scalar(products_stmt)
    payload = {
        **_meta(claims),
        "products": int(products),
        "low_stock": int(low),
        "out_of_stock": int(out_of_stock),
        "expiring_batches": int(expiring_batches),
    }
    return dashboard_views_svc.filter_dashboard_payload(payload, claims)


async def expenses_slice(
    db: AsyncSession, claims: dict, *, company_id: str | None = None
) -> dict:
    tid = claims["tenant_id"]
    total_stmt = select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
        m.Expense.tenant_id == tid,
        m.Expense.status == "approved",
    )
    total_stmt = apply_company_filter(total_stmt, m.Expense.company_id, company_id)
    total = (await db.execute(total_stmt)).scalar() or 0
    by_cat = await expenses_by_category(db, tid, company_id=company_id)
    payload = {
        **_meta(claims),
        "total_expenses": float(total),
        "expenses_by_category": by_cat,
    }
    return dashboard_views_svc.filter_dashboard_payload(payload, claims)


async def expenses_by_category(
    db: AsyncSession, tenant_id: str, *, company_id: str | None = None
) -> list[dict]:
    """Approved expense totals grouped by category name (Stage 84 S1)."""
    cat_name = func.coalesce(m.ExpenseCategory.name, m.Expense.category, "Uncategorized")
    stmt = (
        select(cat_name.label("category"), func.coalesce(func.sum(m.Expense.amount), 0).label("total"))
        .select_from(m.Expense)
        .outerjoin(m.ExpenseCategory, m.ExpenseCategory.id == m.Expense.category_id)
        .where(m.Expense.tenant_id == tenant_id, m.Expense.status == "approved")
        .group_by(cat_name)
        .order_by(func.coalesce(func.sum(m.Expense.amount), 0).desc())
    )
    if company_id:
        stmt = stmt.where(m.Expense.company_id == company_id)
    rows = (await db.execute(stmt)).all()
    return [
        {"category": str(row.category or "Uncategorized"), "total": float(row.total or 0)}
        for row in rows
    ]


async def credit_slice(db: AsyncSession, claims: dict) -> dict:
    """AR outstanding summary for credit:read dashboards (Stage 84 S1)."""
    from app import credit as credit_svc

    aging = await credit_svc.ar_aging(
        db, claims["tenant_id"], company_id=claims.get("company_id")
    )
    total_due = float(aging.get("total_due") or 0)
    payload = {
        **_meta(claims),
        "credit_outstanding": total_due,
        "ar_total_due": total_due,
    }
    return dashboard_views_svc.filter_dashboard_payload(payload, claims)


async def user_stats_slice(db: AsyncSession, claims: dict) -> dict:
    tid = claims["tenant_id"]
    from datetime import timedelta

    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    async def scalar(stmt):
        return (await db.execute(stmt)).scalar() or 0

    user_total = await scalar(select(func.count(m.User.id)).where(m.User.tenant_id == tid))
    user_active = await scalar(
        select(func.count(m.User.id)).where(m.User.tenant_id == tid, m.User.is_active == True)  # noqa: E712
    )
    role_count = await scalar(
        select(func.count(m.CustomRole.id)).where(m.CustomRole.tenant_id == tid)
    )
    recent_logins = await scalar(
        select(func.count(func.distinct(m.AuthSession.user_id))).where(
            m.AuthSession.tenant_id == tid,
            m.AuthSession.revoked_at.is_(None),
            m.AuthSession.created_at >= day_start - timedelta(days=7),
        )
    )
    payload = {
        **_meta(claims),
        "user_stats": {
            "total_users": int(user_total),
            "active_users": int(user_active),
            "inactive_users": int(user_total) - int(user_active),
            "custom_roles": int(role_count),
            "system_roles": len(list_system_role_catalog()),
            "recent_logins_7d": int(recent_logins),
        },
    }
    return dashboard_views_svc.filter_dashboard_payload(payload, claims)


async def summary_slice(
    db: AsyncSession, claims: dict, *, company_id: str | None = None
) -> dict:
    """Compact KPI card payload (permission-filtered)."""
    tid = claims["tenant_id"]

    async def scalar(stmt):
        return (await db.execute(stmt)).scalar() or 0

    sales_stmt = select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
        m.SalesInvoice.tenant_id == tid,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
    )
    sales_stmt = apply_company_filter(sales_stmt, m.SalesInvoice.company_id, company_id)
    sales = float(await scalar(sales_stmt))

    pos_stmt = select(func.coalesce(func.sum(m.Transaction.total), 0)).where(
        m.Transaction.tenant_id == tid,
        m.Transaction.tx_type.in_(["sale", "pos_sale"]),
    )
    pos_stmt = apply_company_filter(pos_stmt, m.Transaction.company_id, company_id)
    pos = float(await scalar(pos_stmt))

    expenses_stmt = select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
        m.Expense.tenant_id == tid,
        m.Expense.status == "approved",
    )
    expenses_stmt = apply_company_filter(expenses_stmt, m.Expense.company_id, company_id)
    expenses = float(await scalar(expenses_stmt))

    products_stmt = select(func.count(m.Product.id)).where(m.Product.tenant_id == tid)
    products_stmt = apply_company_filter(products_stmt, m.Product.company_id, company_id)
    products = int(await scalar(products_stmt))

    low_stmt = select(func.count(m.Product.id)).where(
        m.Product.tenant_id == tid,
        m.Product.stock_qty <= m.Product.reorder_level,
    )
    low_stmt = apply_company_filter(low_stmt, m.Product.company_id, company_id)
    low = int(await scalar(low_stmt))

    customers_stmt = select(func.count(m.Party.id)).where(
        m.Party.tenant_id == tid, m.Party.kind == "customer"
    )
    customers_stmt = apply_company_filter(customers_stmt, m.Party.company_id, company_id)
    customers = int(await scalar(customers_stmt))
    payload = {
        **_meta(claims),
        "total_sales": sales + pos,
        "total_expenses": expenses,
        "products": products,
        "low_stock": low,
        "customers": customers,
    }
    return dashboard_views_svc.filter_dashboard_payload(payload, claims)
