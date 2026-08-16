"""RecommendationService — deterministic recommended actions for insights."""

from __future__ import annotations


class RecommendationService:
    @staticmethod
    def for_insight(insight_type: str, *, context: dict | None = None) -> dict:
        ctx = context or {}
        mapping = {
            "negative_stock": {
                "text": "Investigate stock adjustments and correct inventory balances immediately.",
                "href": "/inventory?tab=stock",
                "cta": "View Stock",
            },
            "out_of_stock": {
                "text": "Create a purchase order or transfer stock for out-of-stock items.",
                "href": "/purchasing",
                "cta": "Open Purchasing",
            },
            "low_stock": {
                "text": "Review stock and create purchase orders for items below reorder level.",
                "href": "/inventory?tab=stock",
                "cta": "View Low Stock",
            },
            "expired_stock": {
                "text": "Quarantine expired batches and remove them from sellable stock.",
                "href": "/inventory?tab=products",
                "cta": "Review Batches",
            },
            "near_expiry": {
                "text": "Consider promotion, transfer, or prioritized sale before expiry.",
                "href": "/inventory?tab=products",
                "cta": "Review Expiry",
            },
            "sales_decline": {
                "text": "Review product mix, promotions, and branch performance for the decline period.",
                "href": "/reports?tab=sales",
                "cta": "View Sales Report",
            },
            "anomaly_sales_drop": {
                "text": "Investigate Unusual Activity against recent averages (not a fraud finding).",
                "href": "/sales",
                "cta": "Review Sales",
            },
            "anomaly_sales_spike": {
                "text": "Confirm Unusual Activity against promotions, bulk orders, or data entry errors.",
                "href": "/sales",
                "cta": "Review Sales",
            },
            "sales_growth": {
                "text": "Consider increasing reorder quantity for accelerating products.",
                "href": "/purchasing",
                "cta": "Review Reorders",
            },
            "expense_spike": {
                "text": "Review expense categories contributing to the increase.",
                "href": "/expenses",
                "cta": "View Expenses",
            },
            "expense_to_sales": {
                "text": "Compare expense categories against sales and tighten discretionary spend.",
                "href": "/reports?tab=summary",
                "cta": "View Summary",
            },
            "credit_overdue": {
                "text": "Follow up with overdue customers and review credit limits.",
                "href": "/credit",
                "cta": "Open Credit",
            },
            "credit_concentration": {
                "text": "Diversify credit exposure and prioritize collection for top debtors.",
                "href": "/credit",
                "cta": "View Aging",
            },
            "dead_stock": {
                "text": "Consider promotion, transfer, bundling, or discontinuation.",
                "href": "/inventory?tab=products",
                "cta": "Review Dead Stock",
            },
            "slow_moving": {
                "text": "Review pricing and promotions for slow-moving items.",
                "href": "/inventory?tab=products",
                "cta": "Review Products",
            },
            "profit_divergence": {
                "text": "Review expenses, discounts, and cost prices — sales up but profit down.",
                "href": "/reports?tab=summary",
                "cta": "Review Profit",
            },
            "supplier_concentration": {
                "text": "Review supplier mix to reduce concentration risk.",
                "href": "/purchasing?tab=suppliers",
                "cta": "View Suppliers",
            },
            "branch_outperform": {
                "text": "Share practices from the stronger location with underperforming branches.",
                "href": "/stores",
                "cta": "Compare Stores",
            },
            "reorder_needed": {
                "text": "Create a purchase order using the Smart Reorder Recommendation quantities.",
                "href": "/purchasing",
                "cta": "Create PO",
            },
            "monthly_summary": {
                "text": "Review the Business Insights dashboard for detailed breakdowns.",
                "href": "/business-insights",
                "cta": "Open Insights",
            },
        }
        base = mapping.get(
            insight_type,
            {
                "text": "Review the related ERP module for details.",
                "href": "/business-insights",
                "cta": "Open Insights",
            },
        )
        if ctx.get("href"):
            base = {**base, "href": ctx["href"]}
        if ctx.get("cta"):
            base = {**base, "cta": ctx["cta"]}
        return base
