"""Tenant dashboard + party history CSV export helpers (Stage 153).

Honesty: dashboard CSV surfaces real tenant KPI aggregates only — no fabricated
MRR or billing Completes (ADR-002). History CSVs reuse customer/supplier history
payloads (activity ledgers), distinct from Stage 119 party roster exports.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


def export_tenant_dashboard_csv(*, dashboard: dict[str, Any]) -> bytes:
    """Flatten GET /dashboard JSON into multi-row_type CSV (Stage 153 B1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "row_type",
            "section",
            "key",
            "value",
            "label",
            "count",
            "generated_at",
        ]
    )
    generated = dashboard.get("generated_at")
    kpi_keys = (
        "total_sales",
        "total_purchases",
        "total_expenses",
        "pending_expenses",
        "credit_outstanding",
        "ar_total_due",
        "ap_total_due",
        "ap_outstanding",
        "profit_summary",
        "income_mtd",
        "products",
        "low_stock",
        "out_of_stock",
        "expiring_batches",
        "customers",
        "suppliers",
        "daily_revenue",
        "yesterday_revenue",
        "dod_change_pct",
        "monthly_revenue",
        "prior_month_revenue",
        "mom_change_pct",
        "view",
        "role_label",
    )
    for key in kpi_keys:
        if key in dashboard:
            writer.writerow(
                [
                    "kpi",
                    "summary",
                    key,
                    _cell(dashboard.get(key)),
                    "",
                    "",
                    _cell(generated),
                ]
            )
    user_stats = dashboard.get("user_stats")
    if isinstance(user_stats, dict):
        for key, value in user_stats.items():
            writer.writerow(
                [
                    "user_stat",
                    "users",
                    _cell(key),
                    _cell(value),
                    "",
                    "",
                    _cell(generated),
                ]
            )
    expenses_by_category = dashboard.get("expenses_by_category")
    if isinstance(expenses_by_category, list):
        for row in expenses_by_category:
            if not isinstance(row, dict):
                continue
            writer.writerow(
                [
                    "expense_category",
                    "expenses",
                    _cell(row.get("category")),
                    _cell(row.get("total")),
                    _cell(row.get("category")),
                    _cell(row.get("total")),
                    _cell(generated),
                ]
            )
    for section, items, label_key, value_keys in (
        ("recent_sales", dashboard.get("recent_sales"), "reference", ("total", "source")),
        ("top_products", dashboard.get("top_products"), "name", ("revenue", "quantity", "sku")),
    ):
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            label = item.get(label_key) or item.get("name") or item.get("sku")
            value = item.get(value_keys[0]) if value_keys else None
            detail_parts = [f"{k}={item.get(k)}" for k in value_keys[1:] if item.get(k) is not None]
            writer.writerow(
                [
                    "list",
                    section,
                    _cell(label),
                    _cell(value),
                    _cell(label),
                    _cell("; ".join(detail_parts) if detail_parts else item.get("quantity")),
                    _cell(generated),
                ]
            )
    for section, series, label_key, value_key in (
        ("daily_revenue_series", dashboard.get("daily_revenue_series"), "date", "revenue"),
        ("monthly_revenue_series", dashboard.get("monthly_revenue_series"), "month", "revenue"),
    ):
        if not isinstance(series, list):
            continue
        for point in series:
            if not isinstance(point, dict):
                continue
            writer.writerow(
                [
                    "series",
                    section,
                    _cell(point.get(label_key)),
                    _cell(point.get(value_key)),
                    _cell(point.get(label_key)),
                    _cell(point.get(value_key)),
                    _cell(generated),
                ]
            )
    store_scope = dashboard.get("store_scope")
    if isinstance(store_scope, dict):
        for key, value in store_scope.items():
            if isinstance(value, (dict, list)):
                value = str(value)
            writer.writerow(
                [
                    "store_scope",
                    "scope",
                    _cell(key),
                    _cell(value),
                    "",
                    "",
                    _cell(generated),
                ]
            )
    return buf.getvalue().encode("utf-8")


def _history_row(
    writer: Any,
    *,
    party_kind: str,
    party_id: str,
    row_type: str,
    item: dict[str, Any],
    number_keys: tuple[str, ...],
) -> None:
    number = ""
    for key in number_keys:
        if item.get(key) is not None:
            number = _cell(item.get(key))
            break
    writer.writerow(
        [
            party_kind,
            party_id,
            row_type,
            _cell(item.get("id")),
            number,
            _cell(item.get("status")),
            _cell(item.get("total_amount") if item.get("total_amount") is not None else item.get("amount")),
            _cell(item.get("payment_method")),
            _cell(item.get("created_at")),
        ]
    )


def export_customer_history_csv(*, history: dict[str, Any]) -> bytes:
    """Flatten GET /customers/{id}/history into multi-row_type CSV (Stage 153 C1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "party_kind",
            "party_id",
            "row_type",
            "record_id",
            "number",
            "status",
            "amount",
            "payment_method",
            "created_at",
        ]
    )
    party_id = _cell(history.get("customer_id"))
    writer.writerow(
        [
            "customer",
            party_id,
            "summary",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    for row_type, key, number_keys in (
        ("invoice", "invoices", ("invoice_number",)),
        ("quotation", "quotations", ("quotation_number",)),
        ("order", "orders", ("order_number",)),
        ("return", "returns", ("return_number",)),
        ("payment", "payments", ("id",)),
    ):
        items = history.get(key) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                _history_row(
                    writer,
                    party_kind="customer",
                    party_id=party_id,
                    row_type=row_type,
                    item=item,
                    number_keys=number_keys,
                )
    return buf.getvalue().encode("utf-8")


def export_supplier_history_csv(*, history: dict[str, Any]) -> bytes:
    """Flatten GET /suppliers/{id}/history into multi-row_type CSV (Stage 153 S1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "party_kind",
            "party_id",
            "row_type",
            "record_id",
            "number",
            "status",
            "amount",
            "payment_method",
            "created_at",
        ]
    )
    party_id = _cell(history.get("supplier_id"))
    writer.writerow(
        [
            "supplier",
            party_id,
            "summary",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    for row_type, key, number_keys in (
        ("order", "orders", ("po_number",)),
        ("invoice", "invoices", ("invoice_number",)),
        ("return", "returns", ("return_number",)),
        ("payment", "payments", ("id",)),
    ):
        items = history.get(key) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                _history_row(
                    writer,
                    party_kind="supplier",
                    party_id=party_id,
                    row_type=row_type,
                    item=item,
                    number_keys=number_keys,
                )
    return buf.getvalue().encode("utf-8")


def export_dashboard_sales_trend_csv(*, payload: dict[str, Any]) -> bytes:
    """Flatten GET /dashboard/sales-trend into series CSV (Stage 157 S1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "row_type",
            "period",
            "revenue",
            "store_scope_mode",
            "role_label",
        ]
    )
    scope = payload.get("store_scope") or {}
    scope_mode = _cell(scope.get("mode") if isinstance(scope, dict) else "")
    role = _cell(payload.get("role_label"))
    for row in payload.get("daily_revenue_series") or []:
        if not isinstance(row, dict):
            continue
        writer.writerow(
            [
                "daily",
                _cell(row.get("date")),
                _cell(row.get("revenue")),
                scope_mode,
                role,
            ]
        )
    for row in payload.get("monthly_revenue_series") or []:
        if not isinstance(row, dict):
            continue
        writer.writerow(
            [
                "monthly",
                _cell(row.get("month")),
                _cell(row.get("revenue")),
                scope_mode,
                role,
            ]
        )
    return buf.getvalue().encode("utf-8")


def export_dashboard_top_products_csv(*, payload: dict[str, Any]) -> bytes:
    """Flatten GET /dashboard/top-products into ranking CSV (Stage 157 T1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "rank",
            "product_id",
            "sku",
            "name",
            "quantity",
            "revenue",
            "store_scope_mode",
            "role_label",
        ]
    )
    scope = payload.get("store_scope") or {}
    scope_mode = _cell(scope.get("mode") if isinstance(scope, dict) else "")
    role = _cell(payload.get("role_label"))
    for idx, row in enumerate(payload.get("top_products") or [], start=1):
        if not isinstance(row, dict):
            continue
        writer.writerow(
            [
                _cell(idx),
                _cell(row.get("id")),
                _cell(row.get("sku")),
                _cell(row.get("name")),
                _cell(row.get("quantity")),
                _cell(row.get("revenue")),
                scope_mode,
                role,
            ]
        )
    return buf.getvalue().encode("utf-8")


def export_dashboard_stock_alerts_csv(*, payload: dict[str, Any]) -> bytes:
    """Flatten GET /dashboard/stock-alerts into KPI CSV (Stage 158 A1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "value", "role_label"])
    role = _cell(payload.get("role_label"))
    for key in ("products", "low_stock", "out_of_stock", "expiring_batches"):
        if key in payload:
            writer.writerow([key, _cell(payload.get(key)), role])
    return buf.getvalue().encode("utf-8")


def export_dashboard_expenses_csv(*, payload: dict[str, Any]) -> bytes:
    """Flatten GET /dashboard/expenses into category CSV (Stage 158 E1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["row_type", "category", "total", "total_expenses", "role_label"])
    role = _cell(payload.get("role_label"))
    writer.writerow(
        [
            "summary",
            "",
            "",
            _cell(payload.get("total_expenses")),
            role,
        ]
    )
    for row in payload.get("expenses_by_category") or []:
        if not isinstance(row, dict):
            continue
        writer.writerow(
            [
                "category",
                _cell(row.get("category")),
                _cell(row.get("total")),
                "",
                role,
            ]
        )
    return buf.getvalue().encode("utf-8")


def export_dashboard_credit_csv(*, payload: dict[str, Any]) -> bytes:
    """Flatten GET /dashboard/credit into AR outstanding CSV (Stage 158 C1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "value", "role_label"])
    role = _cell(payload.get("role_label"))
    for key in ("credit_outstanding", "ar_total_due"):
        if key in payload:
            writer.writerow([key, _cell(payload.get(key)), role])
    return buf.getvalue().encode("utf-8")


def export_dashboard_user_stats_csv(*, payload: dict[str, Any]) -> bytes:
    """Flatten GET /dashboard/user-stats into KPI CSV (Stage 159 U1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "value", "role_label"])
    role = _cell(payload.get("role_label"))
    stats = payload.get("user_stats") or {}
    if isinstance(stats, dict):
        for key in (
            "total_users",
            "active_users",
            "inactive_users",
            "custom_roles",
            "system_roles",
            "recent_logins_7d",
        ):
            if key in stats:
                writer.writerow([key, _cell(stats.get(key)), role])
    return buf.getvalue().encode("utf-8")


def export_dashboard_summary_csv(*, payload: dict[str, Any]) -> bytes:
    """Flatten GET /dashboard/summary into compact KPI CSV (Stage 159 M1)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["metric", "value", "role_label"])
    role = _cell(payload.get("role_label"))
    for key in ("total_sales", "total_expenses", "products", "low_stock", "customers"):
        if key in payload:
            writer.writerow([key, _cell(payload.get(key)), role])
    return buf.getvalue().encode("utf-8")
