"""InsightRulesService — generate structured insights from metrics (no external AI)."""

from __future__ import annotations

from app.bi_defaults import DEFAULT_SETTINGS, PRIORITY_ATTENTION, PRIORITY_WARNING
from app.bi_priority import InsightPriorityService
from app.bi_recommendations import RecommendationService


def _card(
    *,
    insight_type: str,
    category: str,
    priority: str,
    title: str,
    message: str,
    metric_value: float | None = None,
    comparison_value: float | None = None,
    percentage_change: float | None = None,
    related_entity_type: str | None = None,
    related_entity_id: str | None = None,
    context: dict | None = None,
) -> dict:
    rec = RecommendationService.for_insight(insight_type, context=context)
    return {
        "insight_type": insight_type,
        "category": category,
        "priority": priority,
        "title": title,
        "message": message,
        "recommendation": rec["text"],
        "action_href": rec["href"],
        "action_cta": rec["cta"],
        "metric_value": metric_value,
        "comparison_value": comparison_value,
        "percentage_change": percentage_change,
        "related_entity_type": related_entity_type,
        "related_entity_id": related_entity_id,
        "unusual_activity": insight_type.startswith("anomaly_")
        or insight_type in {"expense_spike", "sales_decline"},
    }


class InsightRulesService:
    def __init__(self, settings: dict | None = None):
        self.settings = {**DEFAULT_SETTINGS, **(settings or {})}
        self.priority = InsightPriorityService()

    def build(
        self,
        *,
        sales: dict,
        inventory: dict,
        profit: dict,
        expenses: dict,
        purchases: dict,
        credit: dict | None,
        expiry: dict,
        slow_dead: dict,
        by_store: list[dict],
        reorder: list[dict],
        top_products: list[dict],
        can_financial: bool,
        can_credit: bool,
    ) -> list[dict]:
        insights: list[dict] = []
        decline_thr = float(self.settings.get("sales_decline_warning_pct", 15))
        growth_thr = float(self.settings.get("sales_growth_opportunity_pct", 15))
        exp_thr = float(self.settings.get("expense_increase_warning_pct", 20))
        exp_sales_thr = float(self.settings.get("expense_to_sales_warning_pct", 35))
        conc_thr = float(self.settings.get("credit_concentration_warning_pct", 25))

        # --- Sales ---
        mom = sales.get("mom_change_pct")
        if mom is not None and mom <= -decline_thr:
            insights.append(
                _card(
                    insight_type="sales_decline",
                    category="sales",
                    priority=self.priority.for_sales_decline(pct=mom),
                    title=f"Sales declined {abs(mom):.1f}% vs last month",
                    message=(
                        f"This month sales are {sales['this_month']:.2f} vs last month "
                        f"{sales['last_month']:.2f} ({mom:+.1f}%)."
                    ),
                    metric_value=sales["this_month"],
                    comparison_value=sales["last_month"],
                    percentage_change=mom,
                )
            )
        elif mom is not None and mom >= growth_thr:
            insights.append(
                _card(
                    insight_type="sales_growth",
                    category="sales",
                    priority=self.priority.for_sales_growth(pct=mom),
                    title=f"Sales increased {mom:.1f}% compared with last month",
                    message=(
                        f"This month sales are {sales['this_month']:.2f} vs last month "
                        f"{sales['last_month']:.2f}."
                    ),
                    metric_value=sales["this_month"],
                    comparison_value=sales["last_month"],
                    percentage_change=mom,
                )
            )

        wow = sales.get("wow_change_pct")
        if wow is not None and wow <= -decline_thr:
            insights.append(
                _card(
                    insight_type="sales_decline",
                    category="sales",
                    priority=self.priority.for_sales_decline(pct=wow),
                    title=f"Sales down {abs(wow):.1f}% week-over-week",
                    message=(
                        f"This week {sales['this_week']:.2f} vs last week {sales['last_week']:.2f}."
                    ),
                    metric_value=sales["this_week"],
                    comparison_value=sales["last_week"],
                    percentage_change=wow,
                )
            )

        if top_products:
            best = top_products[0]
            insights.append(
                _card(
                    insight_type="best_seller",
                    category="sales",
                    priority=self.priority.for_information(),
                    title=f"{best['name']} is currently the highest-selling product",
                    message=(
                        f"Revenue {best['revenue']:.2f} on qty {best['qty']:.2f} "
                        f"in the last 30 days."
                    ),
                    metric_value=best["revenue"],
                    related_entity_type="product",
                    related_entity_id=best["product_id"],
                )
            )

        if by_store and len(by_store) >= 2 and by_store[0].get("sales", 0) > 0:
            top = by_store[0]
            total = sum(s.get("sales") or 0 for s in by_store) or 1
            share = round((top["sales"] / total) * 100, 1)
            insights.append(
                _card(
                    insight_type="branch_outperform",
                    category="locations",
                    priority=self.priority.for_information(),
                    title=f"{top['name']} generated {share}% of sales this period",
                    message=f"Leading location sales: {top['sales']:.2f}.",
                    metric_value=top["sales"],
                    percentage_change=share,
                    related_entity_type="store",
                    related_entity_id=top.get("store_id"),
                )
            )

        # --- Inventory ---
        if inventory.get("negative_stock_count", 0) > 0:
            insights.append(
                _card(
                    insight_type="negative_stock",
                    category="inventory",
                    priority=self.priority.for_negative_stock(),
                    title="Negative stock detected",
                    message=(
                        f"{inventory['negative_stock_count']} product(s) show negative on-hand qty. "
                        "Labeled Unusual Activity — investigate adjustments."
                    ),
                    metric_value=float(inventory["negative_stock_count"]),
                )
            )
        if inventory.get("out_of_stock_count", 0) > 0:
            insights.append(
                _card(
                    insight_type="out_of_stock",
                    category="inventory",
                    priority=self.priority.for_out_of_stock(),
                    title=f"{inventory['out_of_stock_count']} products are out of stock",
                    message="Restock or transfer inventory for sellable items.",
                    metric_value=float(inventory["out_of_stock_count"]),
                )
            )
        if inventory.get("low_stock_count", 0) > 0:
            insights.append(
                _card(
                    insight_type="low_stock",
                    category="inventory",
                    priority=self.priority.for_low_stock(),
                    title=f"{inventory['low_stock_count']} products are below reorder level",
                    message="Review stock and create purchase orders where needed.",
                    metric_value=float(inventory["low_stock_count"]),
                )
            )
        if reorder:
            insights.append(
                _card(
                    insight_type="reorder_needed",
                    category="inventory",
                    priority=self.priority.for_low_stock(),
                    title=f"{len(reorder)} Smart Reorder Recommendation(s) ready",
                    message=(
                        "Quantities use average daily sales × (lead time + safety stock) − on hand. "
                        "Not an ML prediction."
                    ),
                    metric_value=float(len(reorder)),
                )
            )
        if slow_dead.get("dead_stock_count", 0) > 0:
            insights.append(
                _card(
                    insight_type="dead_stock",
                    category="inventory",
                    priority=self.priority.for_dead_stock(),
                    title=f"{slow_dead['dead_stock_count']} dead-stock products detected",
                    message=(
                        f"No sales for at least {slow_dead['dead_stock_days']} days "
                        "with stock still on hand."
                    ),
                    metric_value=float(slow_dead["dead_stock_count"]),
                )
            )
        elif slow_dead.get("slow_moving_count", 0) > 0:
            insights.append(
                _card(
                    insight_type="slow_moving",
                    category="inventory",
                    priority=self.priority.for_dead_stock(),
                    title=f"{slow_dead['slow_moving_count']} slow-moving products",
                    message=f"No sales for at least {slow_dead['slow_moving_days']} days.",
                    metric_value=float(slow_dead["slow_moving_count"]),
                )
            )

        # --- Expiry ---
        if expiry.get("expired_count", 0) > 0:
            insights.append(
                _card(
                    insight_type="expired_stock",
                    category="expiry",
                    priority=self.priority.for_expired(),
                    title=f"{expiry['expired_count']} batch(es) already expired",
                    message=(
                        f"Qty at risk {expiry['qty_at_risk']:.2f}; "
                        f"value at risk {expiry['value_at_risk']:.2f}."
                    ),
                    metric_value=float(expiry["expired_count"]),
                )
            )
        for w, payload in (expiry.get("windows") or {}).items():
            cnt = payload.get("count") or 0
            if cnt <= 0:
                continue
            days = int(w)
            insights.append(
                _card(
                    insight_type="near_expiry",
                    category="expiry",
                    priority=self.priority.for_near_expiry(days=days),
                    title=f"{cnt} batch(es) expire within {days} days",
                    message="Consider promotion, transfer, or accelerated sale.",
                    metric_value=float(cnt),
                )
            )

        # --- Expenses ---
        exp_mom = expenses.get("mom_change_pct")
        if exp_mom is not None and exp_mom >= exp_thr:
            insights.append(
                _card(
                    insight_type="expense_spike",
                    category="expenses",
                    priority=self.priority.for_expense_spike(pct=exp_mom),
                    title=f"Expenses increased {exp_mom:.1f}% vs last month",
                    message=(
                        f"This month {expenses['this_month']:.2f} vs last month "
                        f"{expenses['last_month']:.2f}. Unusual Activity — review categories."
                    ),
                    metric_value=expenses["this_month"],
                    comparison_value=expenses["last_month"],
                    percentage_change=exp_mom,
                )
            )
        ratio = expenses.get("expense_to_sales_pct")
        if ratio is not None and ratio >= exp_sales_thr:
            insights.append(
                _card(
                    insight_type="expense_to_sales",
                    category="expenses",
                    priority=self.priority.for_expense_spike(pct=ratio),
                    title=f"Expenses are {ratio:.1f}% of monthly sales",
                    message="Expense-to-sales ratio exceeds the configured warning threshold.",
                    metric_value=ratio,
                )
            )

        # --- Profit (permission gated by caller) ---
        if can_financial:
            rev_chg = profit.get("revenue_change_pct")
            net_chg = profit.get("net_profit_change_pct")
            if (
                rev_chg is not None
                and net_chg is not None
                and rev_chg > 0
                and net_chg < 0
            ):
                insights.append(
                    _card(
                        insight_type="profit_divergence",
                        category="profit",
                        priority=self.priority.for_profit_divergence(),
                        title="Sales up but net profit down",
                        message=(
                            f"Revenue changed {rev_chg:+.1f}% while net profit changed "
                            f"{net_chg:+.1f}%. Review expenses and discounts."
                        ),
                        percentage_change=net_chg,
                        metric_value=profit.get("current", {}).get("net_profit"),
                        comparison_value=profit.get("prior", {}).get("net_profit"),
                    )
                )

        # --- Purchases ---
        suppliers = purchases.get("by_supplier") or []
        if suppliers and suppliers[0].get("share_pct") and suppliers[0]["share_pct"] >= 50:
            s0 = suppliers[0]
            insights.append(
                _card(
                    insight_type="supplier_concentration",
                    category="purchases",
                    priority=self.priority.for_information(),
                    title=f"{s0['name']} accounts for {s0['share_pct']}% of purchases",
                    message="High supplier concentration this period.",
                    metric_value=s0["amount"],
                    percentage_change=s0["share_pct"],
                    related_entity_type="supplier",
                    related_entity_id=s0["supplier_id"],
                )
            )

        # --- Credit ---
        if can_credit and credit:
            total_due = float(credit.get("total_due") or 0)
            totals = credit.get("totals") or {}
            overdue_30 = float(totals.get("31_60") or 0) + float(
                totals.get("61_90") or 0
            ) + float(totals.get("90_plus") or 0)
            if total_due > 0:
                insights.append(
                    _card(
                        insight_type="credit_overdue",
                        category="credit",
                        priority=self.priority.for_credit_overdue(
                            days_bucket="31_60" if overdue_30 else "1_30"
                        ),
                        title=f"{total_due:,.2f} outstanding in customer credit",
                        message=(
                            f"Of which {overdue_30:,.2f} is overdue >30 days "
                            f"(aging buckets from credit.ar_aging)."
                        ),
                        metric_value=total_due,
                        comparison_value=overdue_30,
                    )
                )
            parties = credit.get("parties") or []
            if parties and total_due > 0:
                top = parties[0]
                share = round((float(top.get("total_due") or 0) / total_due) * 100, 1)
                if share >= conc_thr:
                    insights.append(
                        _card(
                            insight_type="credit_concentration",
                            category="credit",
                            priority=self.priority.for_credit_overdue(days_bucket="31_60"),
                            title=(
                                f"{top.get('name')} represents {share}% of outstanding credit"
                            ),
                            message="Highest debtor concentration.",
                            metric_value=float(top.get("total_due") or 0),
                            percentage_change=share,
                            related_entity_type="customer",
                            related_entity_id=top.get("party_id"),
                        )
                    )

        # Unusual Activity (rule-based anomalies — not fraud findings)
        anomaly_pct = float(self.settings.get("sales_anomaly_pct") or 40)
        avg_daily = float(sales.get("avg_daily_sales") or 0)
        today_sales = float(sales.get("today") or 0)
        if avg_daily > 0:
            day_delta = ((today_sales - avg_daily) / avg_daily) * 100
            if day_delta <= -anomaly_pct:
                insights.append(
                    _card(
                        insight_type="anomaly_sales_drop",
                        category="sales",
                        priority=PRIORITY_WARNING,
                        title="Unusual Activity: sales below recent average",
                        message=(
                            f"Today's sales are {abs(day_delta):.1f}% below the recent average daily sales. "
                            "Labeled Unusual Activity — not a fraud finding."
                        ),
                        metric_value=today_sales,
                        comparison_value=avg_daily,
                        percentage_change=round(day_delta, 2),
                    )
                )
            elif day_delta >= anomaly_pct:
                insights.append(
                    _card(
                        insight_type="anomaly_sales_spike",
                        category="sales",
                        priority=PRIORITY_ATTENTION,
                        title="Unusual Activity: sales above recent average",
                        message=(
                            f"Today's sales are {day_delta:.1f}% above the recent average daily sales. "
                            "Labeled Unusual Activity — not a fraud finding."
                        ),
                        metric_value=today_sales,
                        comparison_value=avg_daily,
                        percentage_change=round(day_delta, 2),
                    )
                )

        # Monthly information summary
        insights.append(
            _card(
                insight_type="monthly_summary",
                category="summary",
                priority=self.priority.for_information(),
                title="Monthly performance snapshot",
                message=(
                    f"MTD sales {sales.get('this_month', 0):.2f}; "
                    f"avg daily {sales.get('avg_daily_sales', 0):.2f}; "
                    f"transactions {sales.get('transaction_count_mtd', 0)}."
                ),
                metric_value=sales.get("this_month"),
            )
        )

        insights.sort(key=InsightPriorityService.sort_key)
        return insights
