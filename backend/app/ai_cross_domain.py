"""Cross-domain AI analysis (Stage 25 X1).

Orchestrates proven inventory / sales / purchases / expenses analyzers into one
contract with synthesis signals — no parallel AI stack, no external ML.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app import ai_expenses as ai_expenses_svc
from app import ai_inventory as ai_inventory_svc
from app import ai_purchases as ai_purchases_svc
from app import ai_sales as ai_sales_svc


def _signal(
    *,
    kind: str,
    severity: str,
    title: str,
    summary: str,
    action: str | None = None,
    domains: list[str] | None = None,
    metrics: dict | None = None,
) -> dict:
    return {
        "kind": kind,
        "severity": severity,
        "title": title,
        "summary": summary,
        "action": action,
        "domains": domains or [],
        "metrics": metrics or {},
    }


async def analyze_cross_domain(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | str | None = None,
    to_date: datetime | str | None = None,
    lookback_days: int = 90,
    company_id: str | None = None,
) -> dict:
    """Run domain analyzers and synthesize cross-domain signals."""
    now = datetime.utcnow()
    lookback_days = max(14, min(int(lookback_days), 365))

    sales = await ai_sales_svc.analyze_sales(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        lookback_days=lookback_days,
        company_id=company_id,
    )
    purchases = await ai_purchases_svc.analyze_purchases(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        lookback_days=lookback_days,
        company_id=company_id,
    )
    expenses = await ai_expenses_svc.analyze_expenses(
        db,
        tenant_id,
        from_date=from_date or sales["from_date"],
        to_date=to_date or sales["to_date"],
        company_id=company_id,
    )
    low = await ai_inventory_svc.predict_low_stock(
        db,
        tenant_id,
        lookback_days=min(lookback_days, 60),
        horizon_days=14,
        lead_time_days=7,
        at_risk_only=True,
        company_id=company_id,
    )
    dead = await ai_inventory_svc.identify_dead_stock(
        db,
        tenant_id,
        lookback_days=min(lookback_days, 90),
        company_id=company_id,
    )

    sales_summary = sales.get("summary") or {}
    purch_summary = purchases.get("summary") or {}
    exp_summary = expenses.get("summary") or {}
    at_risk = list(low.get("predictions") or [])
    dead_items = list(dead.get("items") or dead.get("products") or [])
    # identify_dead_stock may use "count" + list under different keys
    if not dead_items and isinstance(dead.get("dead_stock"), list):
        dead_items = dead["dead_stock"]

    inventory_summary = {
        "at_risk_count": int(low.get("at_risk_count") or len(at_risk)),
        "dead_stock_count": int(dead.get("count") or len(dead_items)),
        "method": low.get("method") or "rules_v1",
        "top_at_risk": [
            {
                "product_id": p.get("product_id"),
                "name": p.get("name"),
                "days_to_stockout": p.get("days_to_stockout"),
                "suggested_order_qty": p.get("suggested_order_qty"),
                "confidence": p.get("confidence"),
            }
            for p in at_risk[:5]
        ],
    }

    domains = {
        "inventory": {
            "summary": inventory_summary,
            "endpoint": "GET /ai/inventory/low-stock-prediction",
        },
        "sales": {
            "summary": {
                "invoice_count": sales_summary.get("invoice_count"),
                "total_sales": sales_summary.get("total_sales"),
                "avg_daily_sales": sales_summary.get("avg_daily_sales"),
                "customer_count": sales_summary.get("customer_count"),
                "trend_direction": sales_summary.get("trend_direction"),
                "daily_slope": sales_summary.get("daily_slope"),
            },
            "endpoint": "GET /ai/sales/analysis",
        },
        "purchases": {
            "summary": {
                "purchase_order_count": purch_summary.get("purchase_order_count"),
                "open_po_count": purch_summary.get("open_po_count"),
                "open_po_value": purch_summary.get("open_po_value"),
                "grn_count": purch_summary.get("grn_count"),
                "total_spend": purch_summary.get("total_spend"),
                "supplier_count": purch_summary.get("supplier_count"),
                "overdue_invoice_count": purch_summary.get("overdue_invoice_count"),
                "trend_direction": purch_summary.get("trend_direction"),
                "top_supplier_spend_share": purch_summary.get("top_supplier_spend_share"),
            },
            "endpoint": "GET /ai/purchases/analysis",
        },
        "expenses": {
            "summary": {
                "expense_count": exp_summary.get("expense_count"),
                "approved_count": exp_summary.get("approved_count"),
                "pending_count": exp_summary.get("pending_count"),
                "total_approved": exp_summary.get("total_approved"),
                "total_pending": exp_summary.get("total_pending"),
                "wow_change_pct": exp_summary.get("wow_change_pct"),
                "anomaly_count": len(expenses.get("anomalies") or []),
                "over_budget_count": (expenses.get("budget_variance") or {}).get(
                    "over_budget_count"
                ),
            },
            "endpoint": "GET /ai/expenses/analysis",
        },
    }

    signals: list[dict] = []
    total_sales = float(sales_summary.get("total_sales") or 0)
    total_spend = float(purch_summary.get("total_spend") or 0)
    total_exp = float(exp_summary.get("total_approved") or 0)
    sales_dir = sales_summary.get("trend_direction")
    purch_dir = purch_summary.get("trend_direction")
    open_po = int(purch_summary.get("open_po_count") or 0)
    at_risk_n = inventory_summary["at_risk_count"]
    overdue_n = int(purch_summary.get("overdue_invoice_count") or 0)
    top_share = float(purch_summary.get("top_supplier_spend_share") or 0)
    exp_wow = exp_summary.get("wow_change_pct")

    if sales_dir == "up" and purch_dir in ("flat", "down") and total_sales > 0:
        signals.append(
            _signal(
                kind="sales_up_purchases_lag",
                severity="medium",
                title="Sales rising while purchase spend lags",
                summary=(
                    f"Sales trend is up (slope {sales_summary.get('daily_slope')}) but "
                    f"purchase spend trend is {purch_dir}."
                ),
                action="Review reorder suggestions and open POs before stockouts.",
                domains=["sales", "purchases"],
                metrics={
                    "sales_trend": sales_dir,
                    "purchases_trend": purch_dir,
                    "total_sales": total_sales,
                    "total_spend": total_spend,
                },
            )
        )

    if at_risk_n > 0 and open_po == 0:
        signals.append(
            _signal(
                kind="stockout_without_open_po",
                severity="high",
                title=f"{at_risk_n} SKU(s) at stockout risk with no open POs",
                summary="Inventory risk exists but purchasing has no open commitments in range.",
                action="Create draft POs from Inventory → Low stock or AI restock cards.",
                domains=["inventory", "purchases"],
                metrics={"at_risk_count": at_risk_n, "open_po_count": open_po},
            )
        )
    elif at_risk_n > 0 and open_po > 0:
        signals.append(
            _signal(
                kind="stockout_with_open_po",
                severity="medium",
                title=f"{at_risk_n} at-risk SKU(s) while {open_po} PO(s) remain open",
                summary="Chase partial/open receipts so inbound stock covers predicted demand.",
                action="Check PO fill on Purchasing and AI purchases analysis.",
                domains=["inventory", "purchases"],
                metrics={"at_risk_count": at_risk_n, "open_po_count": open_po},
            )
        )

    if total_sales > 0 and total_exp > 0 and total_exp >= total_sales * 0.5:
        signals.append(
            _signal(
                kind="expenses_heavy_vs_sales",
                severity="high" if total_exp >= total_sales else "medium",
                title="Approved expenses are high relative to sales",
                summary=(
                    f"Approved expenses {total_exp:.2f} vs sales {total_sales:.2f} "
                    f"in the analysis window."
                ),
                action="Review expense anomalies and over-budget categories.",
                domains=["expenses", "sales"],
                metrics={"total_approved_expenses": total_exp, "total_sales": total_sales},
            )
        )

    if total_sales > 0 and total_spend > 0:
        spend_ratio = round(total_spend / total_sales, 3)
        if spend_ratio >= 0.85:
            signals.append(
                _signal(
                    kind="purchase_spend_vs_sales",
                    severity="high" if spend_ratio >= 1.0 else "medium",
                    title="Purchase spend near or above sales",
                    summary=(
                        f"Purchase invoice spend {total_spend:.2f} is {spend_ratio:.0%} of "
                        f"sales {total_sales:.2f}."
                    ),
                    action="Validate large PIs and supplier concentration before cash outflow.",
                    domains=["purchases", "sales"],
                    metrics={
                        "total_spend": total_spend,
                        "total_sales": total_sales,
                        "spend_to_sales": spend_ratio,
                    },
                )
            )

    if top_share >= 0.6 and sales_dir == "up":
        signals.append(
            _signal(
                kind="supplier_concentration_with_growth",
                severity="medium",
                title="Sales growing with concentrated supplier spend",
                summary=(
                    f"Top supplier share is {top_share:.0%} while sales trend is up — "
                    "sourcing risk may grow with volume."
                ),
                action="Diversify suppliers or lock volume terms.",
                domains=["purchases", "sales"],
                metrics={"top_supplier_spend_share": top_share, "sales_trend": sales_dir},
            )
        )

    if overdue_n > 0 and (
        (isinstance(exp_wow, (int, float)) and exp_wow >= 40) or total_exp > total_sales > 0
    ):
        signals.append(
            _signal(
                kind="cash_pressure",
                severity="high",
                title="Overdue supplier bills with elevated expense pressure",
                summary=(
                    f"{overdue_n} overdue purchase invoice(s); expenses "
                    f"{'up ' + str(exp_wow) + '% WoW' if exp_wow is not None else 'elevated vs sales'}."
                ),
                action="Prioritize AP schedule and discretionary expense pause.",
                domains=["purchases", "expenses"],
                metrics={
                    "overdue_invoice_count": overdue_n,
                    "expense_wow_change_pct": exp_wow,
                    "total_approved_expenses": total_exp,
                },
            )
        )

    if inventory_summary["dead_stock_count"] > 0 and sales_dir == "down":
        signals.append(
            _signal(
                kind="dead_stock_with_soft_sales",
                severity="medium",
                title="Dead stock present while sales trend soft",
                summary=(
                    f"{inventory_summary['dead_stock_count']} dead-stock item(s) with sales trend "
                    f"{sales_dir}."
                ),
                action="Promote or markdown slow movers; pause reorders on those SKUs.",
                domains=["inventory", "sales"],
                metrics={
                    "dead_stock_count": inventory_summary["dead_stock_count"],
                    "sales_trend": sales_dir,
                },
            )
        )

    # Always include a healthy baseline signal when domains have data but no alerts
    domain_activity = sum(
        1
        for key, block in domains.items()
        if any(
            v not in (None, 0, 0.0, [], {})
            for v in (block.get("summary") or {}).values()
        )
    )

    return {
        "generated_at": now,
        "from_date": sales.get("from_date"),
        "to_date": sales.get("to_date"),
        "method": "rules_v1",
        "lookback_days": lookback_days,
        "summary": {
            "domains_analyzed": ["inventory", "sales", "purchases", "expenses"],
            "domains_with_activity": domain_activity,
            "cross_signal_count": len(signals),
            "total_sales": total_sales,
            "total_purchase_spend": total_spend,
            "total_approved_expenses": total_exp,
            "at_risk_sku_count": at_risk_n,
            "overdue_purchase_invoice_count": overdue_n,
        },
        "domains": domains,
        "cross_signals": signals,
        "note": (
            "Orchestrates existing domain analyzers (inventory/sales/purchases/expenses). "
            "Not an external LLM or Prophet model."
        ),
    }
