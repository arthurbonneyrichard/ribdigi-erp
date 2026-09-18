"""Smart Business Intelligence — defaults, priorities, and formula documentation.

Layer 1 is fully deterministic. No external LLM / AI API is used.
"""

from __future__ import annotations

# Priority levels (user-facing)
PRIORITY_CRITICAL = "CRITICAL"
PRIORITY_WARNING = "WARNING"
PRIORITY_ATTENTION = "ATTENTION"
PRIORITY_OPPORTUNITY = "OPPORTUNITY"
PRIORITY_INFORMATION = "INFORMATION"

PRIORITY_RANK = {
    PRIORITY_CRITICAL: 0,
    PRIORITY_WARNING: 1,
    PRIORITY_ATTENTION: 2,
    PRIORITY_OPPORTUNITY: 3,
    PRIORITY_INFORMATION: 4,
}

INSIGHT_STATUS_ACTIVE = "ACTIVE"
INSIGHT_STATUS_ACKNOWLEDGED = "ACKNOWLEDGED"
INSIGHT_STATUS_RESOLVED = "RESOLVED"
INSIGHT_STATUS_DISMISSED = "DISMISSED"

# Persist only these priorities to business_insights history
PERSIST_PRIORITIES = frozenset({PRIORITY_CRITICAL, PRIORITY_WARNING})

DEFAULT_SETTINGS: dict = {
    # Inventory
    "slow_moving_days": 30,
    "dead_stock_days": 60,
    "expiry_warning_days": [7, 30, 60],
    "safety_stock_days": 7,
    "default_lead_time_days": 7,
    # Sales / expenses
    "sales_decline_warning_pct": 15.0,
    "sales_growth_opportunity_pct": 15.0,
    "expense_increase_warning_pct": 20.0,
    "expense_to_sales_warning_pct": 35.0,
    # Credit
    "credit_overdue_attention_days": 30,
    "credit_concentration_warning_pct": 25.0,
    # Anomaly
    "sales_anomaly_pct": 40.0,
    "large_discount_pct": 25.0,
    # Health score weights (must sum to 100)
    "health_weights": {
        "sales": 25,
        "inventory": 20,
        "profitability": 20,
        "credit": 20,
        "expenses": 15,
    },
}

# Formula documentation exposed via GET /business-insights/formulas
FORMULA_DOCS: list[dict] = [
    {
        "metric": "average_daily_sales_qty",
        "formula": "qty_sold_in_period / max(days_in_period, 1)",
        "source": "sales_invoice_items joined to posted sales_invoices",
        "notes": "Cancelled/void/draft invoices excluded via posted status filter.",
    },
    {
        "metric": "estimated_days_remaining",
        "formula": "current_stock / average_daily_sales_qty when average_daily_sales_qty > 0 else null",
        "source": "products.stock_qty + sales velocity",
    },
    {
        "metric": "recommended_reorder_qty",
        "formula": (
            "max(0, ceil((average_daily_sales_qty * (lead_time_days + safety_stock_days)) "
            "- current_stock - pending_incoming_qty))"
        ),
        "source": "products + open purchase orders (partially_received/sent)",
        "notes": (
            "Labeled Smart Reorder Recommendation — not ML prediction. "
            "POST /business-insights/reorder-requests converts lines into draft PRs "
            "grouped by last supplier (or an explicit fallback supplier_id)."
        ),
    },
    {
        "metric": "sales_change_pct",
        "formula": "((current - prior) / prior) * 100 when prior > 0 else null",
        "source": "sales_invoices.total_amount for posted statuses",
    },
    {
        "metric": "gross_profit",
        "formula": "revenue - cogs",
        "source": "sales_invoice_items line totals vs product.cost_price * qty",
        "notes": "When cost_price missing/zero, COGS contribution is 0 and margin flagged incomplete.",
    },
    {
        "metric": "business_health_score",
        "formula": (
            "weighted average of component scores (0-100) using configured health_weights; "
            "components: sales trend, inventory health, profitability, credit risk, expense control"
        ),
        "source": "derived metrics from ERP tables",
    },
    {
        "metric": "credit_aging_buckets",
        "formula": "reuse credit.ar_aging buckets: current, 1_30, 31_60, 61_90, 90_plus",
        "source": "sales_invoices open balances via credit.ar_aging",
    },
]

POSTED_SALES_STATUSES = frozenset({"posted", "sent", "partial", "paid", "overdue"})
POSTED_PURCHASE_STATUSES = frozenset({"unpaid", "partial", "paid", "overdue"})
OPEN_PO_STATUSES = frozenset({"sent", "partially_received"})
OPEN_PR_STATUSES = frozenset({"draft", "pending", "approved"})
APPROVED_EXPENSE_STATUS = "approved"
