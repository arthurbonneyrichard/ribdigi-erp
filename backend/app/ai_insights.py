"""Deterministic AI dashboard insights (Phase 4 / BR-21.2).

Uses real tenant sales/expense/inventory signals — no external LLM required.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

POSTED_INVOICE_STATUSES = frozenset({"posted", "sent", "partial", "paid", "overdue"})


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
    }


async def _period_sales(
    db: AsyncSession, tenant_id: str, start: datetime, end: datetime
) -> float:
    return float(
        (
            await db.execute(
                select(func.coalesce(func.sum(m.SalesInvoice.total_amount), 0)).where(
                    m.SalesInvoice.tenant_id == tenant_id,
                    m.SalesInvoice.status.in_(list(POSTED_INVOICE_STATUSES)),
                    m.SalesInvoice.created_at >= start,
                    m.SalesInvoice.created_at < end,
                )
            )
        ).scalar_one()
        or 0
    )


async def _period_expenses(
    db: AsyncSession, tenant_id: str, start: datetime, end: datetime
) -> float:
    return float(
        (
            await db.execute(
                select(func.coalesce(func.sum(m.Expense.amount), 0)).where(
                    m.Expense.tenant_id == tenant_id,
                    m.Expense.status == "approved",
                    m.Expense.expense_date >= start,
                    m.Expense.expense_date < end,
                )
            )
        ).scalar_one()
        or 0
    )


async def generate_insights(db: AsyncSession, tenant_id: str) -> dict:
    """Build structured insight cards from tenant operational data."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    month_ago = now - timedelta(days=30)
    two_months_ago = now - timedelta(days=60)

    insights: list[dict] = []

    # --- Sales WoW / MoM ---
    sales_this_week = await _period_sales(db, tenant_id, week_ago, now)
    sales_prev_week = await _period_sales(db, tenant_id, two_weeks_ago, week_ago)
    sales_this_month = await _period_sales(db, tenant_id, month_ago, now)
    sales_prev_month = await _period_sales(db, tenant_id, two_months_ago, month_ago)

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
                )
            )

    # --- Expense anomalies ---
    exp_this_week = await _period_expenses(db, tenant_id, week_ago, now)
    exp_prev_week = await _period_expenses(db, tenant_id, two_weeks_ago, week_ago)
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
                )
            )

    # --- Restock / velocity suggestions ---
    from app import ai_inventory as ai_inventory_svc

    pred = await ai_inventory_svc.predict_low_stock(
        db, tenant_id, horizon_days=14, at_risk_only=True
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
            )
        )

    # --- Classic reorder-level low stock ---
    low = (
        await db.execute(
            select(func.count())
            .select_from(m.Product)
            .where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active == True,  # noqa: E712
                m.Product.stock_qty <= m.Product.reorder_level,
            )
        )
    ).scalar_one()
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
            )
        )

    # Severity order
    rank = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda x: (rank.get(x["severity"], 9), x["kind"], x["title"]))

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
    }


async def publish_insights(
    db: AsyncSession,
    tenant_id: str,
    *,
    send_weekly_digest: bool = True,
) -> dict:
    """Create notifications for high-severity insights; optionally email weekly digest."""
    from app.notifications import create_notification

    payload = await generate_insights(db, tenant_id)
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
            )
            digest_sent = True
            created += 1

    await db.flush()
    return {
        "insight_count": payload["count"],
        "notifications_created": created,
        "weekly_digest_sent": digest_sent,
    }
