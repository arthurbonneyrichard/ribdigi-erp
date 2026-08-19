"""Deterministic AI dashboard insights (Phase 4 / BR-21.2 + Stage 25 B1).

Uses real tenant inventory / sales / purchases / expense signals — no external LLM.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.reports import apply_company_filter

POSTED_INVOICE_STATUSES = frozenset({"posted", "sent", "partial", "paid", "overdue"})
POSTED_PI_STATUSES = frozenset({"unpaid", "partial", "paid", "overdue"})
OPEN_PO_STATUSES = frozenset({"sent", "partially_received"})
ACTUALS = ("inventory", "sales", "purchases", "expenses")


def _insight(
    *,
    kind: str,
    severity: str,
    title: str,
    summary: str,
    action: str | None = None,
    metrics: dict | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    domains: list[str] | None = None,
) -> dict:
    return {
        "id": f"{kind}:{entity_id or 'tenant'}",
        "kind": kind,
        "severity": severity,
        "title": title,
        "summary": summary,
        "action": action,
        "metrics": metrics or {},
        "entity_type": entity_type,
        "entity_id": entity_id,
        "domains": list(domains or []),
    }


async def _period_sales(
    db: AsyncSession,
    tenant_id: str,
    start: datetime,
    end: datetime,
    company_id: str | None = None,
) -> float:
    stmt = select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(list(POSTED_INVOICE_STATUSES)),
        m.SalesInvoice.created_at >= start,
        m.SalesInvoice.created_at < end,
    )
    stmt = apply_company_filter(stmt, m.SalesInvoice.company_id, company_id)
    return float((await db.execute(stmt)).scalar_one() or 0)


async def _period_expenses(
    db: AsyncSession,
    tenant_id: str,
    start: datetime,
    end: datetime,
    company_id: str | None = None,
) -> float:
    stmt = select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
        m.Expense.tenant_id == tenant_id,
        m.Expense.status == "approved",
        m.Expense.expense_date >= start,
        m.Expense.expense_date < end,
    )
    stmt = apply_company_filter(stmt, m.Expense.company_id, company_id)
    return float((await db.execute(stmt)).scalar_one() or 0)


async def _period_purchases(
    db: AsyncSession,
    tenant_id: str,
    start: datetime,
    end: datetime,
    company_id: str | None = None,
) -> float:
    stmt = select(func.coalesce(func.sum(m.PurchaseInvoice.total_amount), 0)).where(
        m.PurchaseInvoice.tenant_id == tenant_id,
        m.PurchaseInvoice.status.in_(list(POSTED_PI_STATUSES)),
        m.PurchaseInvoice.invoice_date >= start,
        m.PurchaseInvoice.invoice_date < end,
    )
    stmt = apply_company_filter(stmt, m.PurchaseInvoice.company_id, company_id)
    return float((await db.execute(stmt)).scalar_one() or 0)


async def generate_insights(
    db: AsyncSession, tenant_id: str, company_id: str | None = None
) -> dict:
    """Build structured insight cards from tenant operational data."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)

    insights: list[dict] = []

    # --- Sales WoW / MoM ---
    sales_this_week = await _period_sales(
        db, tenant_id, week_ago, now, company_id=company_id
    )
    sales_prev_week = await _period_sales(
        db, tenant_id, two_weeks_ago, week_ago, company_id=company_id
    )
    sales_this_month = await _period_sales(
        db, tenant_id, month_ago, now, company_id=company_id
    )
    sales_prev_month = await _period_sales(
        db, tenant_id, two_months_ago, month_ago, company_id=company_id
    )

    if sales_prev_week > 0:
        wow_pct = round(((sales_this_week - sales_prev_week) / sales_prev_week) * 100, 1)
        if abs(wow_pct) >= 25:
            direction = "up" if wow_pct > 0 else "down"
            insights.append(
                _insight(
                    kind="sales_wow",
                    severity="high" if abs(wow_pct) >= 40 else "medium",
                    title=f"Sales {direction} {abs(wow_pct):.0f}% week-over-week",
                    summary=(
                        f"This week sales are {sales_this_week:.2f} vs prior week "
                        f"{sales_prev_week:.2f} ({wow_pct:+.1f}%)."
                    ),
                    action="Review daily sales and top products for the shift.",
                    metrics={
                        "this_week": sales_this_week,
                        "prior_week": sales_prev_week,
                        "change_pct": wow_pct,
                    },
                    domains=["sales"],
                )
            )
    elif sales_this_week > 0 and sales_prev_week == 0:
        insights.append(
            _insight(
                kind="sales_wow",
                severity="medium",
                title="Sales resumed after a quiet prior week",
                summary=f"This week recorded {sales_this_week:.2f} with no sales in the prior week.",
                action="Confirm POS/invoice posting is running normally.",
                metrics={"this_week": sales_this_week, "prior_week": 0, "change_pct": None},
                domains=["sales"],
            )
        )

    if sales_prev_month > 0:
        mom_pct = round(((sales_this_month - sales_prev_month) / sales_prev_month) * 100, 1)
        if abs(mom_pct) >= 20:
            direction = "up" if mom_pct > 0 else "down"
            insights.append(
                _insight(
                    kind="sales_mom",
                    severity="medium",
                    title=f"Sales {direction} {abs(mom_pct):.0f}% vs prior 30 days",
                    summary=(
                        f"Last 30 days: {sales_this_month:.2f}; prior 30 days: "
                        f"{sales_prev_month:.2f} ({mom_pct:+.1f}%)."
                    ),
                    action="Compare product mix and promotions across the two periods.",
                    metrics={
                        "this_period": sales_this_month,
                        "prior_period": sales_prev_month,
                        "change_pct": mom_pct,
                    },
                    domains=["sales"],
                )
            )

    # --- Expense anomalies ---
    exp_this_week = await _period_expenses(
        db, tenant_id, week_ago, now, company_id=company_id
    )
    exp_prev_week = await _period_expenses(
        db, tenant_id, two_weeks_ago, week_ago, company_id=company_id
    )
    if exp_prev_week > 0:
        exp_pct = round(((exp_this_week - exp_prev_week) / exp_prev_week) * 100, 1)
        if exp_pct >= 35:
            insights.append(
                _insight(
                    kind="expense_spike",
                    severity="high" if exp_pct >= 60 else "medium",
                    title=f"Expenses up {exp_pct:.0f}% week-over-week",
                    summary=(
                        f"Approved expenses this week {exp_this_week:.2f} vs prior week "
                        f"{exp_prev_week:.2f}."
                    ),
                    action="Review pending and approved expenses by category/budget.",
                    metrics={
                        "this_week": exp_this_week,
                        "prior_week": exp_prev_week,
                        "change_pct": exp_pct,
                    },
                    domains=["expenses"],
                )
            )

    if sales_this_month > 0 and exp_this_week > sales_this_week and sales_this_week >= 0:
        # week expenses vs week sales
        if exp_this_week > sales_this_week and sales_this_week > 0:
            insights.append(
                _insight(
                    kind="expense_vs_sales",
                    severity="high",
                    title="Weekly expenses exceed weekly sales",
                    summary=(
                        f"Approved expenses {exp_this_week:.2f} exceed sales "
                        f"{sales_this_week:.2f} this week."
                    ),
                    action="Tighten discretionary spend and check large recurring items.",
                    metrics={"expenses": exp_this_week, "sales": sales_this_week},
                    domains=["expenses", "sales"],
                )
            )

    # --- Purchases actuals (Stage 25 B1) ---
    purch_this_week = await _period_purchases(
        db, tenant_id, week_ago, now, company_id=company_id
    )
    purch_prev_week = await _period_purchases(
        db, tenant_id, two_weeks_ago, week_ago, company_id=company_id
    )
    if purch_prev_week > 0:
        purch_pct = round(((purch_this_week - purch_prev_week) / purch_prev_week) * 100, 1)
        if abs(purch_pct) >= 35:
            direction = "up" if purch_pct > 0 else "down"
            insights.append(
                _insight(
                    kind="purchase_spend_wow",
                    severity="high" if abs(purch_pct) >= 60 else "medium",
                    title=f"Purchase spend {direction} {abs(purch_pct):.0f}% week-over-week",
                    summary=(
                        f"Posted purchase invoices this week {purch_this_week:.2f} vs prior week "
                        f"{purch_prev_week:.2f} ({purch_pct:+.1f}%)."
                    ),
                    action="Confirm large receipts/invoices and review AI purchases analysis.",
                    metrics={
                        "this_week": purch_this_week,
                        "prior_week": purch_prev_week,
                        "change_pct": purch_pct,
                    },
                    domains=["purchases"],
                )
            )

    overdue_pi_stmt = (
        select(func.count())
        .select_from(m.PurchaseInvoice)
        .where(
            m.PurchaseInvoice.tenant_id == tenant_id,
            m.PurchaseInvoice.status == "overdue",
        )
    )
    overdue_pi_stmt = apply_company_filter(
        overdue_pi_stmt, m.PurchaseInvoice.company_id, company_id
    )
    overdue_pi_n = int((await db.execute(overdue_pi_stmt)).scalar_one() or 0)
    # Also count unpaid/partial past due_date
    past_due_stmt = (
        select(func.count())
        .select_from(m.PurchaseInvoice)
        .where(
            m.PurchaseInvoice.tenant_id == tenant_id,
            m.PurchaseInvoice.status.in_(["unpaid", "partial", "overdue"]),
            m.PurchaseInvoice.due_date.is_not(None),
            m.PurchaseInvoice.due_date < now,
            (m.PurchaseInvoice.total_amount - m.PurchaseInvoice.paid_amount) > 0.001,
        )
    )
    past_due_stmt = apply_company_filter(
        past_due_stmt, m.PurchaseInvoice.company_id, company_id
    )
    past_due_n = int((await db.execute(past_due_stmt)).scalar_one() or 0)
    overdue_n = max(overdue_pi_n, past_due_n)
    if overdue_n > 0:
        insights.append(
            _insight(
                kind="purchase_overdue_bills",
                severity="high",
                title=f"{overdue_n} overdue purchase invoice(s)",
                summary="Supplier bills are past due — AP cash pressure may affect operations.",
                action="Open Purchasing / supplier payments or AI purchases analysis overdue list.",
                metrics={"overdue_count": overdue_n},
                domains=["purchases"],
            )
        )

    open_po_stmt = (
        select(func.count())
        .select_from(m.PurchaseOrder)
        .where(
            m.PurchaseOrder.tenant_id == tenant_id,
            m.PurchaseOrder.status.in_(list(OPEN_PO_STATUSES)),
        )
    )
    open_po_stmt = apply_company_filter(
        open_po_stmt, m.PurchaseOrder.company_id, company_id
    )
    open_po_n = int((await db.execute(open_po_stmt)).scalar_one() or 0)
    draft_po_stmt = (
        select(func.count())
        .select_from(m.PurchaseOrder)
        .where(
            m.PurchaseOrder.tenant_id == tenant_id,
            m.PurchaseOrder.status == "draft",
        )
    )
    draft_po_stmt = apply_company_filter(
        draft_po_stmt, m.PurchaseOrder.company_id, company_id
    )
    draft_po_n = int((await db.execute(draft_po_stmt)).scalar_one() or 0)
    if draft_po_n >= 3:
        insights.append(
            _insight(
                kind="purchase_draft_po_backlog",
                severity="medium",
                title=f"{draft_po_n} draft purchase order(s) unsent",
                summary="Draft POs inflate planning noise until sent or cancelled.",
                action="Review Purchasing drafts; send or cancel stale orders.",
                metrics={"draft_count": draft_po_n, "open_po_count": open_po_n},
                domains=["purchases"],
            )
        )

    # Cross actual: sales rising vs purchases lagging (lightweight; X1 has full synthesis)
    if (
        sales_prev_week > 0
        and sales_this_week >= sales_prev_week * 1.25
        and purch_this_week <= purch_prev_week
        and sales_this_week > 0
    ):
        insights.append(
            _insight(
                kind="sales_up_purchases_lag",
                severity="medium",
                title="Sales rising while purchase spend lags",
                summary=(
                    f"Sales this week {sales_this_week:.2f} (prior {sales_prev_week:.2f}) while "
                    f"purchase spend {purch_this_week:.2f} (prior {purch_prev_week:.2f})."
                ),
                action="Check restock suggestions and open POs before stockouts.",
                metrics={
                    "sales_this_week": sales_this_week,
                    "sales_prior_week": sales_prev_week,
                    "purchases_this_week": purch_this_week,
                    "purchases_prior_week": purch_prev_week,
                },
                domains=["sales", "purchases"],
            )
        )

    # --- Restock / velocity suggestions ---
    from app import ai_inventory as ai_inventory_svc

    pred = await ai_inventory_svc.predict_low_stock(
        db, tenant_id, horizon_days=14, at_risk_only=True, company_id=company_id
    )
    for p in pred["predictions"][:5]:
        if p.get("confidence", 0) < 0.25:
            continue
        days = p.get("days_to_stockout")
        seasonality = float(p.get("seasonality_factor") or 1)
        sales_up = seasonality >= 1.25
        action = (
            f"Restock {p['name']} — sales up {int((seasonality - 1) * 100)}% recently; "
            f"order ~{p['suggested_order_qty']}."
            if sales_up
            else f"Restock {p['name']} — predicted stockout in ~{days} day(s); "
            f"suggested qty {p['suggested_order_qty']}."
        )
        insights.append(
            _insight(
                kind="restock_suggestion",
                severity="high" if days is not None and days <= 7 else "medium",
                title=f"Restock {p['name']}",
                summary=action,
                action="Create a draft PO from Inventory → Low stock or Purchasing.",
                metrics={
                    "days_to_stockout": days,
                    "suggested_order_qty": p["suggested_order_qty"],
                    "confidence": p["confidence"],
                    "seasonality_factor": seasonality,
                },
                entity_type="product",
                entity_id=p["product_id"],
                domains=["inventory", "sales"],
            )
        )

    # --- Classic reorder-level low stock ---
    low_stmt = (
        select(func.count())
        .select_from(m.Product)
        .where(
            m.Product.tenant_id == tenant_id,
            m.Product.is_active == True,  # noqa: E712
            m.Product.stock_qty <= m.Product.reorder_level,
        )
    )
    low_stmt = apply_company_filter(low_stmt, m.Product.company_id, company_id)
    low = (await db.execute(low_stmt)).scalar_one()
    low_n = int(low or 0)
    if low_n > 0:
        insights.append(
            _insight(
                kind="low_stock",
                severity="medium",
                title=f"{low_n} product(s) at or below reorder level",
                summary="Current on-hand quantity is at or under the configured reorder level.",
                action="Open Inventory → Low stock to reorder.",
                metrics={"count": low_n},
                domains=["inventory"],
            )
        )

    if low_n > 0 and open_po_n == 0:
        insights.append(
            _insight(
                kind="stockout_without_open_po",
                severity="high",
                title="Low stock with no open purchase orders",
                summary=(
                    f"{low_n} product(s) at/below reorder level and no open/draft/sent POs "
                    "to cover inbound supply."
                    if draft_po_n == 0
                    else f"{low_n} product(s) low; open PO commitments are thin "
                    f"(draft-only count {draft_po_n})."
                ),
                action="Create or send purchase orders from Low stock / Purchasing.",
                metrics={"low_stock_count": low_n, "open_po_count": open_po_n, "draft_count": draft_po_n},
                domains=["inventory", "purchases"],
            )
        )

    # Severity order
    rank = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: (rank.get(x["severity"], 9), x["kind"], x["title"]))

    covered = sorted({d for i in insights for d in (i.get("domains") or []) if d in ACTUALS})
    summaries = [i["summary"] for i in insights]
    return {
        "generated_at": now,
        "method": "rules_v1",
        "count": len(insights),
        "insights": insights,
        # Backward-compatible string list for older clients / isolation tests
        "summaries": summaries
        or ["No urgent anomaly detected from the currently configured business rules."],
        "low_stock_predictions": {
            "at_risk_count": pred["at_risk_count"],
            "method": pred["method"],
        },
        "actuals_covered": covered,
        "actuals": list(ACTUALS),
        "note": (
            "Business insights from actual Inventory, Sales, Purchases, and Expenses "
            "(Stage 25 B1). Rule-based — not an external LLM."
        ),
    }


async def publish_insights(
    db: AsyncSession,
    tenant_id: str,
    *,
    send_weekly_digest: bool = True,
    company_id: str | None = None,
) -> dict:
    """Create notifications for high-severity insights; optionally email weekly digest."""
    from app.notifications import create_notification

    payload = await generate_insights(db, tenant_id, company_id=company_id)
    created = 0
    for item in payload["insights"]:
        if item["severity"] != "high":
            continue
        existing = (
            await db.execute(
                select(m.Notification).where(
                    m.Notification.tenant_id == tenant_id,
                    m.Notification.category == "ai_insight",
                    m.Notification.entity_id == (item.get("entity_id") or item["kind"]),
                    m.Notification.status == "unread",
                    m.Notification.title == item["title"],
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        await create_notification(
            db,
            tenant_id=tenant_id,
            category="ai_insight",
            title=item["title"],
            message=item["summary"] + (f" Suggested: {item['action']}" if item.get("action") else ""),
            entity_type=item.get("entity_type") or "ai_insight",
            entity_id=item.get("entity_id") or item["kind"],
            company_id=company_id,
        )
        created += 1

    digest_sent = False
    if send_weekly_digest:
        week_ago = datetime.utcnow() - timedelta(days=7)
        prior = (
            await db.execute(
                select(m.Notification).where(
                    m.Notification.tenant_id == tenant_id,
                    m.Notification.category == "ai_insight",
                    m.Notification.title == "Weekly AI Insight Digest",
                    m.Notification.created_at >= week_ago,
                )
            )
        ).scalar_one_or_none()
        if not prior and payload["insights"]:
            lines = [f"- [{i['severity']}] {i['title']}: {i['summary']}" for i in payload["insights"][:8]]
            body = "Weekly AI insight digest:\n" + "\n".join(lines)
            await create_notification(
                db,
                tenant_id=tenant_id,
                category="ai_insight",
                title="Weekly AI Insight Digest",
                message=body,
                entity_type="ai_insight",
                entity_id="weekly_digest",
                company_id=company_id,
            )
            digest_sent = True
            created += 1

    await db.flush()
    return {
        "insight_count": payload["count"],
        "notifications_created": created,
        "weekly_digest_sent": digest_sent,
    }
