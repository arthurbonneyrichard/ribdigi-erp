"""InsightPriorityService — map rule outcomes to CRITICAL/WARNING/… levels."""

from __future__ import annotations

from app.bi_defaults import (
    PRIORITY_ATTENTION,
    PRIORITY_CRITICAL,
    PRIORITY_INFORMATION,
    PRIORITY_OPPORTUNITY,
    PRIORITY_RANK,
    PRIORITY_WARNING,
)


class InsightPriorityService:
    @staticmethod
    def sort_key(insight: dict) -> tuple:
        return (
            PRIORITY_RANK.get(insight.get("priority") or PRIORITY_INFORMATION, 9),
            insight.get("category") or "",
            insight.get("title") or "",
        )

    @staticmethod
    def for_negative_stock() -> str:
        return PRIORITY_CRITICAL

    @staticmethod
    def for_out_of_stock(*, high_demand: bool = False) -> str:
        return PRIORITY_CRITICAL if high_demand else PRIORITY_WARNING

    @staticmethod
    def for_low_stock() -> str:
        return PRIORITY_WARNING

    @staticmethod
    def for_expired() -> str:
        return PRIORITY_CRITICAL

    @staticmethod
    def for_near_expiry(*, days: int) -> str:
        if days <= 7:
            return PRIORITY_WARNING
        return PRIORITY_ATTENTION

    @staticmethod
    def for_sales_decline(*, pct: float, consecutive_weeks: bool = False) -> str:
        if consecutive_weeks or abs(pct) >= 25:
            return PRIORITY_WARNING
        return PRIORITY_ATTENTION

    @staticmethod
    def for_sales_growth(*, pct: float) -> str:
        return PRIORITY_OPPORTUNITY if pct >= 15 else PRIORITY_INFORMATION

    @staticmethod
    def for_expense_spike(*, pct: float) -> str:
        return PRIORITY_WARNING if pct >= 20 else PRIORITY_ATTENTION

    @staticmethod
    def for_credit_overdue(*, days_bucket: str) -> str:
        if days_bucket in ("61_90", "90_plus"):
            return PRIORITY_CRITICAL
        if days_bucket in ("31_60",):
            return PRIORITY_WARNING
        return PRIORITY_ATTENTION

    @staticmethod
    def for_dead_stock() -> str:
        return PRIORITY_ATTENTION

    @staticmethod
    def for_profit_divergence() -> str:
        return PRIORITY_WARNING

    @staticmethod
    def for_information() -> str:
        return PRIORITY_INFORMATION
