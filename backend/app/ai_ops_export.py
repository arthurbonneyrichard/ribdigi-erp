"""CSV export for AI security alerts, report templates, business insights (Stage 145),
inventory low-stock / forecast / dead-stock predictions (Stage 146),
sales / expense / purchases analysis (Stage 147),
chat history / customer insights / cross-domain analysis (Stage 148),
and document analyze results (Stage 149)."""

from __future__ import annotations

import csv
import io
import json

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from app import ai_chat as ai_chat_svc
from app import ai_cross_domain as ai_cross_domain_svc
from app import ai_customers as ai_customers_svc
from app import ai_documents as ai_documents_svc
from app import ai_expenses as ai_expenses_svc
from app import ai_insights as ai_insights_svc
from app import ai_inventory as ai_inventory_svc
from app import ai_purchases as ai_purchases_svc
from app import ai_reports as ai_reports_svc
from app import ai_sales as ai_sales_svc
from app import ai_security as ai_security_svc
from app.session_passkey_doc_export import _cell

SECURITY_ALERT_EXPORT_COLUMNS = [
    "id",
    "kind",
    "title",
    "detail",
    "severity",
    "score",
    "entity_type",
    "entity_id",
    "detected_at",
    "lookback_hours",
]

REPORT_TEMPLATE_EXPORT_COLUMNS = [
    "id",
    "name",
    "prompt",
    "report_type",
    "format",
    "params",
    "user_id",
    "created_at",
    "updated_at",
]

INSIGHT_EXPORT_COLUMNS = [
    "id",
    "kind",
    "severity",
    "title",
    "summary",
    "action",
    "entity_type",
    "entity_id",
    "domains",
    "metrics",
    "generated_at",
]

LOW_STOCK_EXPORT_COLUMNS = [
    "product_id",
    "sku",
    "name",
    "available_qty",
    "stock_qty",
    "reorder_level",
    "velocity_per_day",
    "adjusted_velocity_per_day",
    "seasonality_factor",
    "days_to_stockout",
    "horizon_days",
    "lead_time_days",
    "suggested_order_qty",
    "confidence",
    "status",
    "at_risk",
]

DEMAND_FORECAST_EXPORT_COLUMNS = [
    "product_id",
    "sku",
    "name",
    "available_qty",
    "stock_qty",
    "reorder_level",
    "velocity_per_day",
    "adjusted_velocity_per_day",
    "seasonality",
    "seasonality_factor",
    "forecast_7d",
    "forecast_30d",
    "forecast_90d",
    "optimal_reorder_qty",
    "confidence",
    "status",
    "last_sale_at",
]

DEAD_STOCK_EXPORT_COLUMNS = [
    "product_id",
    "sku",
    "name",
    "stock_qty",
    "cost_price",
    "estimated_carrying_cost",
    "last_sale_at",
    "days_without_sale",
    "lookback_days",
]

SALES_ANALYSIS_EXPORT_COLUMNS = [
    "row_type",
    "generated_at",
    "from_date",
    "to_date",
    "method",
    "invoice_count",
    "total_sales",
    "avg_daily_sales",
    "customer_count",
    "trend_direction",
    "daily_slope",
    "forecast_7d",
    "forecast_14d",
    "forecast_30d",
    "rfm_segment",
    "rfm_count",
    "rfm_customer_count",
    "product_a_id",
    "product_a_name",
    "product_b_id",
    "product_b_name",
    "co_occurrence_count",
    "support",
    "baskets_with_2plus_lines",
    "peak_hour",
    "peak_weekday",
    "peak_weekday_label",
]

EXPENSE_ANALYSIS_EXPORT_COLUMNS = [
    "row_type",
    "generated_at",
    "from_date",
    "to_date",
    "method",
    "expense_count",
    "approved_count",
    "pending_count",
    "total_approved",
    "total_pending",
    "avg_approved_amount",
    "with_attachment",
    "wow_change_pct",
    "over_budget_count",
    "expense_id",
    "category",
    "description",
    "amount",
    "expense_date",
    "severity",
    "reasons",
    "suggestion_kind",
    "suggestion_category",
    "suggestion_summary",
    "suggestion_action",
]

PURCHASES_ANALYSIS_EXPORT_COLUMNS = [
    "row_type",
    "generated_at",
    "from_date",
    "to_date",
    "method",
    "purchase_order_count",
    "open_po_count",
    "open_po_value",
    "grn_count",
    "purchase_invoice_count",
    "total_spend",
    "avg_daily_spend",
    "supplier_count",
    "overdue_invoice_count",
    "trend_direction",
    "daily_slope",
    "wow_change_pct",
    "top_supplier_spend_share",
    "supplier_id",
    "supplier_name",
    "supplier_invoice_count",
    "supplier_spend",
    "supplier_spend_share",
    "purchase_invoice_id",
    "invoice_number",
    "invoice_status",
    "due_date",
    "balance",
    "total_amount",
    "suggestion_kind",
    "suggestion_severity",
    "suggestion_summary",
    "suggestion_action",
]

CHAT_HISTORY_EXPORT_COLUMNS = [
    "id",
    "message",
    "answer",
    "intent",
    "created_at",
]

CUSTOMER_INSIGHTS_EXPORT_COLUMNS = [
    "row_type",
    "generated_at",
    "lookback_days",
    "method",
    "customer_count",
    "customer_id",
    "name",
    "code",
    "credit_limit",
    "balance",
    "recency_days",
    "frequency",
    "monetary",
    "open_invoice_balance",
    "churn_score",
    "churn_band",
    "churn_reasons",
    "last_purchase_at",
    "promotion_type",
    "promotion_label",
    "promotion_suggestion",
    "discount_pct",
]

CROSS_DOMAIN_EXPORT_COLUMNS = [
    "row_type",
    "generated_at",
    "from_date",
    "to_date",
    "method",
    "lookback_days",
    "domains_analyzed",
    "domains_with_activity",
    "cross_signal_count",
    "total_sales",
    "total_purchase_spend",
    "total_approved_expenses",
    "at_risk_sku_count",
    "overdue_purchase_invoice_count",
    "signal_kind",
    "signal_severity",
    "signal_title",
    "signal_summary",
    "signal_action",
    "signal_domains",
    "signal_metrics",
]

DOCUMENT_ANALYZE_EXPORT_COLUMNS = [
    "row_type",
    "generated_at",
    "method",
    "document_type",
    "filename",
    "content_type",
    "ocr_engine",
    "ocr_confidence",
    "field_name",
    "field_value",
    "match_kind",
    "entity_id",
    "entity_name",
    "entity_kind",
    "match_type",
    "confidence",
    "discrepancy_field",
    "severity",
    "detail",
    "warning",
]


def _json_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), default=str)
    return _cell(value)


async def export_security_alerts_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    lookback_hours: int = 72,
) -> str:
    """Stage 145 S1 — AI security alert rows (audit-derived; no secrets)."""
    data = await ai_security_svc.scan_security_alerts(
        db, tenant_id, lookback_hours=lookback_hours, notify=False
    )
    lookback = data.get("lookback_hours")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SECURITY_ALERT_EXPORT_COLUMNS)
    writer.writeheader()
    for alert in data.get("alerts") or []:
        writer.writerow(
            {
                "id": _cell(alert.get("id")),
                "kind": _cell(alert.get("kind")),
                "title": _cell(alert.get("title")),
                "detail": _cell(alert.get("detail")),
                "severity": _cell(alert.get("severity")),
                "score": _cell(alert.get("score")),
                "entity_type": _cell(alert.get("entity_type")),
                "entity_id": _cell(alert.get("entity_id")),
                "detected_at": _cell(alert.get("detected_at")),
                "lookback_hours": _cell(lookback),
            }
        )
    return buf.getvalue()


async def export_report_templates_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None = None,
) -> str:
    """Stage 145 T1 — saved AI report templates CSV."""
    rows = await ai_reports_svc.list_templates(db, tenant_id, user_id=user_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=REPORT_TEMPLATE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = ai_reports_svc.serialize_template(row)
        writer.writerow(
            {
                "id": _cell(data.get("id")),
                "name": _cell(data.get("name")),
                "prompt": _cell(data.get("prompt")),
                "report_type": _cell(data.get("report_type")),
                "format": _cell(data.get("format")),
                "params": _json_cell(data.get("params")),
                "user_id": _cell(data.get("user_id")),
                "created_at": _cell(data.get("created_at")),
                "updated_at": _cell(data.get("updated_at")),
            }
        )
    return buf.getvalue()


async def export_business_insights_csv(db: AsyncSession, *, tenant_id: str) -> str:
    """Stage 145 I1 — business insight cards CSV (rule-based; not LLM transcripts)."""
    data = await ai_insights_svc.generate_insights(db, tenant_id)
    generated_at = data.get("generated_at")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=INSIGHT_EXPORT_COLUMNS)
    writer.writeheader()
    for card in data.get("insights") or []:
        writer.writerow(
            {
                "id": _cell(card.get("id")),
                "kind": _cell(card.get("kind")),
                "severity": _cell(card.get("severity")),
                "title": _cell(card.get("title")),
                "summary": _cell(card.get("summary")),
                "action": _cell(card.get("action")),
                "entity_type": _cell(card.get("entity_type")),
                "entity_id": _cell(card.get("entity_id")),
                "domains": _json_cell(card.get("domains")),
                "metrics": _json_cell(card.get("metrics")),
                "generated_at": _cell(generated_at),
            }
        )
    return buf.getvalue()


async def export_low_stock_predictions_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    lookback_days: int = 30,
    horizon_days: int = 14,
    lead_time_days: int = 7,
    at_risk_only: bool = False,
) -> str:
    """Stage 146 L1 — low-stock prediction rows CSV."""
    data = await ai_inventory_svc.predict_low_stock(
        db,
        tenant_id,
        lookback_days=lookback_days,
        horizon_days=horizon_days,
        lead_time_days=lead_time_days,
        at_risk_only=at_risk_only,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=LOW_STOCK_EXPORT_COLUMNS)
    writer.writeheader()
    for row in data.get("predictions") or []:
        writer.writerow({k: _cell(row.get(k)) for k in LOW_STOCK_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_demand_forecast_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    lookback_days: int = 30,
    lead_time_days: int = 7,
    product_id: str | None = None,
) -> str:
    """Stage 146 F1 — demand forecast rows CSV."""
    data = await ai_inventory_svc.forecast_demand(
        db,
        tenant_id,
        lookback_days=lookback_days,
        lead_time_days=lead_time_days,
        product_id=product_id,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=DEMAND_FORECAST_EXPORT_COLUMNS)
    writer.writeheader()
    for row in data.get("forecasts") or []:
        writer.writerow({k: _cell(row.get(k)) for k in DEMAND_FORECAST_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_dead_stock_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    lookback_days: int = 90,
    min_stock: float = 0,
) -> str:
    """Stage 146 K1 — dead-stock items CSV."""
    data = await ai_inventory_svc.identify_dead_stock(
        db,
        tenant_id,
        lookback_days=lookback_days,
        min_stock=min_stock,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=DEAD_STOCK_EXPORT_COLUMNS)
    writer.writeheader()
    for row in data.get("items") or []:
        writer.writerow({k: _cell(row.get(k)) for k in DEAD_STOCK_EXPORT_COLUMNS})
    return buf.getvalue()


def _blank_row(columns: list[str]) -> dict[str, str]:
    return {k: "" for k in columns}


async def export_sales_analysis_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    lookback_days: int = 90,
) -> str:
    """Stage 147 S1 — sales analysis multi-section CSV (summary / RFM / affinity / peaks)."""
    data = await ai_sales_svc.analyze_sales(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        lookback_days=lookback_days,
    )
    summary = data.get("summary") or {}
    trend = data.get("trend") or {}
    forecast = trend.get("forecast_totals") or {}
    rfm = data.get("rfm") or {}
    affinity = data.get("product_affinity") or {}
    peaks = data.get("peaks") or {}

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SALES_ANALYSIS_EXPORT_COLUMNS)
    writer.writeheader()

    meta = {
        "generated_at": _cell(data.get("generated_at")),
        "from_date": _cell(data.get("from_date")),
        "to_date": _cell(data.get("to_date")),
        "method": _cell(data.get("method")),
    }

    summary_row = _blank_row(SALES_ANALYSIS_EXPORT_COLUMNS)
    summary_row.update(
        {
            **meta,
            "row_type": "summary",
            "invoice_count": _cell(summary.get("invoice_count")),
            "total_sales": _cell(summary.get("total_sales")),
            "avg_daily_sales": _cell(summary.get("avg_daily_sales")),
            "customer_count": _cell(summary.get("customer_count")),
            "trend_direction": _cell(summary.get("trend_direction")),
            "daily_slope": _cell(summary.get("daily_slope")),
            "forecast_7d": _cell(forecast.get("7")),
            "forecast_14d": _cell(forecast.get("14")),
            "forecast_30d": _cell(forecast.get("30")),
            "rfm_customer_count": _cell(rfm.get("count")),
            "baskets_with_2plus_lines": _cell(affinity.get("baskets_with_2plus_lines")),
            "peak_hour": _cell(peaks.get("peak_hour")),
            "peak_weekday": _cell(peaks.get("peak_weekday")),
            "peak_weekday_label": _cell(peaks.get("peak_weekday_label")),
        }
    )
    writer.writerow(summary_row)

    for segment, count in (rfm.get("segment_counts") or {}).items():
        row = _blank_row(SALES_ANALYSIS_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "rfm_segment",
                "rfm_segment": _cell(segment),
                "rfm_count": _cell(count),
                "rfm_customer_count": _cell(rfm.get("count")),
            }
        )
        writer.writerow(row)

    for pair in affinity.get("pairs") or []:
        row = _blank_row(SALES_ANALYSIS_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "affinity",
                "product_a_id": _cell(pair.get("product_a_id")),
                "product_a_name": _cell(pair.get("product_a_name")),
                "product_b_id": _cell(pair.get("product_b_id")),
                "product_b_name": _cell(pair.get("product_b_name")),
                "co_occurrence_count": _cell(pair.get("co_occurrence_count")),
                "support": _cell(pair.get("support")),
                "baskets_with_2plus_lines": _cell(affinity.get("baskets_with_2plus_lines")),
            }
        )
        writer.writerow(row)

    peak_row = _blank_row(SALES_ANALYSIS_EXPORT_COLUMNS)
    peak_row.update(
        {
            **meta,
            "row_type": "peak",
            "peak_hour": _cell(peaks.get("peak_hour")),
            "peak_weekday": _cell(peaks.get("peak_weekday")),
            "peak_weekday_label": _cell(peaks.get("peak_weekday_label")),
        }
    )
    writer.writerow(peak_row)
    return buf.getvalue()


async def export_expense_analysis_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> str:
    """Stage 147 E1 — expense analysis multi-section CSV (summary / anomalies / suggestions)."""
    data = await ai_expenses_svc.analyze_expenses(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
    )
    summary = data.get("summary") or {}
    budget = data.get("budget_variance") or {}

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPENSE_ANALYSIS_EXPORT_COLUMNS)
    writer.writeheader()

    meta = {
        "generated_at": _cell(data.get("generated_at")),
        "from_date": _cell(data.get("from_date")),
        "to_date": _cell(data.get("to_date")),
        "method": _cell(data.get("method")),
    }

    summary_row = _blank_row(EXPENSE_ANALYSIS_EXPORT_COLUMNS)
    summary_row.update(
        {
            **meta,
            "row_type": "summary",
            "expense_count": _cell(summary.get("expense_count")),
            "approved_count": _cell(summary.get("approved_count")),
            "pending_count": _cell(summary.get("pending_count")),
            "total_approved": _cell(summary.get("total_approved")),
            "total_pending": _cell(summary.get("total_pending")),
            "avg_approved_amount": _cell(summary.get("avg_approved_amount")),
            "with_attachment": _cell(summary.get("with_attachment")),
            "wow_change_pct": _cell(summary.get("wow_change_pct")),
            "over_budget_count": _cell(budget.get("over_budget_count")),
        }
    )
    writer.writerow(summary_row)

    for anomaly in data.get("anomalies") or []:
        row = _blank_row(EXPENSE_ANALYSIS_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "anomaly",
                "expense_id": _cell(anomaly.get("expense_id")),
                "category": _cell(anomaly.get("category")),
                "description": _cell(anomaly.get("description")),
                "amount": _cell(anomaly.get("amount")),
                "expense_date": _cell(anomaly.get("expense_date")),
                "severity": _cell(anomaly.get("severity")),
                "reasons": _json_cell(anomaly.get("reasons")),
            }
        )
        writer.writerow(row)

    for suggestion in data.get("optimization_suggestions") or []:
        row = _blank_row(EXPENSE_ANALYSIS_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "suggestion",
                "suggestion_kind": _cell(suggestion.get("kind")),
                "suggestion_category": _cell(suggestion.get("category")),
                "suggestion_summary": _cell(suggestion.get("summary")),
                "suggestion_action": _cell(suggestion.get("action")),
            }
        )
        writer.writerow(row)
    return buf.getvalue()


async def export_purchases_analysis_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    lookback_days: int = 90,
) -> str:
    """Stage 147 P1 — purchases analysis multi-section CSV (summary / suppliers / overdue / suggestions)."""
    data = await ai_purchases_svc.analyze_purchases(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        lookback_days=lookback_days,
    )
    summary = data.get("summary") or {}
    suppliers = data.get("suppliers") or {}
    invoices = data.get("purchase_invoices") or {}

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PURCHASES_ANALYSIS_EXPORT_COLUMNS)
    writer.writeheader()

    meta = {
        "generated_at": _cell(data.get("generated_at")),
        "from_date": _cell(data.get("from_date")),
        "to_date": _cell(data.get("to_date")),
        "method": _cell(data.get("method")),
    }

    summary_row = _blank_row(PURCHASES_ANALYSIS_EXPORT_COLUMNS)
    summary_row.update(
        {
            **meta,
            "row_type": "summary",
            "purchase_order_count": _cell(summary.get("purchase_order_count")),
            "open_po_count": _cell(summary.get("open_po_count")),
            "open_po_value": _cell(summary.get("open_po_value")),
            "grn_count": _cell(summary.get("grn_count")),
            "purchase_invoice_count": _cell(summary.get("purchase_invoice_count")),
            "total_spend": _cell(summary.get("total_spend")),
            "avg_daily_spend": _cell(summary.get("avg_daily_spend")),
            "supplier_count": _cell(summary.get("supplier_count")),
            "overdue_invoice_count": _cell(summary.get("overdue_invoice_count")),
            "trend_direction": _cell(summary.get("trend_direction")),
            "daily_slope": _cell(summary.get("daily_slope")),
            "wow_change_pct": _cell(summary.get("wow_change_pct")),
            "top_supplier_spend_share": _cell(summary.get("top_supplier_spend_share")),
        }
    )
    writer.writerow(summary_row)

    for supplier in suppliers.get("rows") or []:
        row = _blank_row(PURCHASES_ANALYSIS_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "supplier",
                "supplier_id": _cell(supplier.get("supplier_id")),
                "supplier_name": _cell(supplier.get("supplier_name")),
                "supplier_invoice_count": _cell(supplier.get("invoice_count")),
                "supplier_spend": _cell(supplier.get("spend")),
                "supplier_spend_share": _cell(supplier.get("spend_share")),
            }
        )
        writer.writerow(row)

    for inv in invoices.get("overdue") or []:
        row = _blank_row(PURCHASES_ANALYSIS_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "overdue",
                "purchase_invoice_id": _cell(inv.get("purchase_invoice_id")),
                "invoice_number": _cell(inv.get("invoice_number")),
                "invoice_status": _cell(inv.get("status")),
                "due_date": _cell(inv.get("due_date")),
                "balance": _cell(inv.get("balance")),
                "total_amount": _cell(inv.get("total_amount")),
                "supplier_id": _cell(inv.get("supplier_id")),
                "supplier_name": _cell(inv.get("supplier_name")),
            }
        )
        writer.writerow(row)

    for suggestion in data.get("suggestions") or []:
        row = _blank_row(PURCHASES_ANALYSIS_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "suggestion",
                "suggestion_kind": _cell(suggestion.get("kind")),
                "suggestion_severity": _cell(suggestion.get("severity")),
                "suggestion_summary": _cell(suggestion.get("summary")),
                "suggestion_action": _cell(suggestion.get("action")),
            }
        )
        writer.writerow(row)
    return buf.getvalue()


async def export_chat_history_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    limit: int = 50,
) -> str:
    """Stage 148 C1 — current-user AI chat history CSV (no structured payload dump)."""
    items = await ai_chat_svc.list_history(
        db, tenant_id=tenant_id, user_id=user_id, limit=limit
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CHAT_HISTORY_EXPORT_COLUMNS)
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "id": _cell(item.get("id")),
                "message": _cell(item.get("message")),
                "answer": _cell(item.get("answer")),
                "intent": _cell(item.get("intent")),
                "created_at": _cell(item.get("created_at")),
            }
        )
    return buf.getvalue()


async def export_customer_insights_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    lookback_days: int = 180,
) -> str:
    """Stage 148 I1 — customer intelligence multi-section CSV."""
    data = await ai_customers_svc.customer_intelligence(
        db, tenant_id, lookback_days=lookback_days
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CUSTOMER_INSIGHTS_EXPORT_COLUMNS)
    writer.writeheader()

    meta = {
        "generated_at": _cell(data.get("generated_at")),
        "lookback_days": _cell(data.get("lookback_days")),
        "method": _cell(data.get("method")),
    }

    summary_row = _blank_row(CUSTOMER_INSIGHTS_EXPORT_COLUMNS)
    summary_row.update(
        {
            **meta,
            "row_type": "summary",
            "customer_count": _cell(data.get("customer_count")),
        }
    )
    writer.writerow(summary_row)

    def _customer_row(row_type: str, cust: dict) -> dict[str, str]:
        churn = cust.get("churn") or {}
        promo = cust.get("promotion") or {}
        row = _blank_row(CUSTOMER_INSIGHTS_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": row_type,
                "customer_count": _cell(data.get("customer_count")),
                "customer_id": _cell(cust.get("customer_id")),
                "name": _cell(cust.get("name")),
                "code": _cell(cust.get("code")),
                "credit_limit": _cell(cust.get("credit_limit")),
                "balance": _cell(cust.get("balance")),
                "recency_days": _cell(cust.get("recency_days")),
                "frequency": _cell(cust.get("frequency")),
                "monetary": _cell(cust.get("monetary")),
                "open_invoice_balance": _cell(cust.get("open_invoice_balance")),
                "churn_score": _cell(churn.get("score")),
                "churn_band": _cell(churn.get("band")),
                "churn_reasons": _json_cell(churn.get("reasons")),
                "last_purchase_at": _cell(cust.get("last_purchase_at")),
                "promotion_type": _cell(promo.get("type")),
                "promotion_label": _cell(promo.get("label")),
                "promotion_suggestion": _cell(promo.get("suggestion")),
                "discount_pct": _cell(promo.get("discount_pct")),
            }
        )
        return row

    for cust in data.get("best_customers") or []:
        writer.writerow(_customer_row("best_customer", cust))
    for cust in data.get("churn_risks") or []:
        writer.writerow(_customer_row("churn_risk", cust))
    for promo in data.get("promotion_suggestions") or []:
        row = _blank_row(CUSTOMER_INSIGHTS_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "promotion",
                "customer_id": _cell(promo.get("customer_id")),
                "name": _cell(promo.get("name")),
                "churn_band": _cell(promo.get("churn_band")),
                "promotion_type": _cell(promo.get("type")),
                "promotion_label": _cell(promo.get("label")),
                "promotion_suggestion": _cell(promo.get("suggestion")),
                "discount_pct": _cell(promo.get("discount_pct")),
            }
        )
        writer.writerow(row)
    return buf.getvalue()


async def export_cross_domain_analysis_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    from_date: str | None = None,
    to_date: str | None = None,
    lookback_days: int = 90,
) -> str:
    """Stage 148 X1 — cross-domain analysis multi-section CSV (summary / signals)."""
    data = await ai_cross_domain_svc.analyze_cross_domain(
        db,
        tenant_id,
        from_date=from_date,
        to_date=to_date,
        lookback_days=lookback_days,
    )
    summary = data.get("summary") or {}
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CROSS_DOMAIN_EXPORT_COLUMNS)
    writer.writeheader()

    meta = {
        "generated_at": _cell(data.get("generated_at")),
        "from_date": _cell(data.get("from_date")),
        "to_date": _cell(data.get("to_date")),
        "method": _cell(data.get("method")),
        "lookback_days": _cell(data.get("lookback_days")),
    }

    summary_row = _blank_row(CROSS_DOMAIN_EXPORT_COLUMNS)
    summary_row.update(
        {
            **meta,
            "row_type": "summary",
            "domains_analyzed": _json_cell(summary.get("domains_analyzed")),
            "domains_with_activity": _json_cell(summary.get("domains_with_activity")),
            "cross_signal_count": _cell(summary.get("cross_signal_count")),
            "total_sales": _cell(summary.get("total_sales")),
            "total_purchase_spend": _cell(summary.get("total_purchase_spend")),
            "total_approved_expenses": _cell(summary.get("total_approved_expenses")),
            "at_risk_sku_count": _cell(summary.get("at_risk_sku_count")),
            "overdue_purchase_invoice_count": _cell(
                summary.get("overdue_purchase_invoice_count")
            ),
        }
    )
    writer.writerow(summary_row)

    for signal in data.get("cross_signals") or []:
        row = _blank_row(CROSS_DOMAIN_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "signal",
                "signal_kind": _cell(signal.get("kind")),
                "signal_severity": _cell(signal.get("severity")),
                "signal_title": _cell(signal.get("title")),
                "signal_summary": _cell(signal.get("summary")),
                "signal_action": _cell(signal.get("action")),
                "signal_domains": _json_cell(signal.get("domains")),
                "signal_metrics": _json_cell(signal.get("metrics")),
            }
        )
        writer.writerow(row)
    return buf.getvalue()


def document_analyze_result_to_csv(data: dict) -> str:
    """Flatten document analyze JSON into multi-section CSV (no raw OCR blob dump)."""
    ocr = data.get("ocr") or {}
    fields = data.get("extracted_fields") or {}
    matches = data.get("matches") or {}
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=DOCUMENT_ANALYZE_EXPORT_COLUMNS)
    writer.writeheader()

    meta = {
        "generated_at": _cell(data.get("generated_at")),
        "method": _cell(data.get("method")),
        "document_type": _cell(data.get("document_type")),
        "filename": _cell(data.get("filename")),
        "content_type": _cell(data.get("content_type")),
    }

    summary = _blank_row(DOCUMENT_ANALYZE_EXPORT_COLUMNS)
    summary.update(
        {
            **meta,
            "row_type": "summary",
            "ocr_engine": _cell(ocr.get("engine")),
            "ocr_confidence": _cell(ocr.get("confidence")),
        }
    )
    writer.writerow(summary)

    for name, value in fields.items():
        row = _blank_row(DOCUMENT_ANALYZE_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "field",
                "field_name": _cell(name),
                "field_value": _cell(value),
            }
        )
        writer.writerow(row)

    party = matches.get("party")
    if party:
        row = _blank_row(DOCUMENT_ANALYZE_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "match",
                "match_kind": "party",
                "entity_id": _cell(party.get("id")),
                "entity_name": _cell(party.get("name")),
                "entity_kind": _cell(party.get("kind")),
                "match_type": _cell(party.get("match")),
                "confidence": _cell(party.get("confidence")),
            }
        )
        writer.writerow(row)

    for product in matches.get("products") or []:
        row = _blank_row(DOCUMENT_ANALYZE_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "match",
                "match_kind": "product",
                "entity_id": _cell(product.get("id")),
                "entity_name": _cell(product.get("name") or product.get("sku")),
                "entity_kind": "product",
                "match_type": _cell(product.get("match")),
                "confidence": _cell(product.get("confidence")),
            }
        )
        writer.writerow(row)

    for disc in data.get("discrepancies") or []:
        if isinstance(disc, str):
            detail = disc
            field = ""
            severity = ""
        else:
            detail = disc.get("detail") or disc.get("message") or ""
            field = disc.get("field") or ""
            severity = disc.get("severity") or ""
        row = _blank_row(DOCUMENT_ANALYZE_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "discrepancy",
                "discrepancy_field": _cell(field),
                "severity": _cell(severity),
                "detail": _cell(detail),
            }
        )
        writer.writerow(row)

    for warning in data.get("warnings") or []:
        row = _blank_row(DOCUMENT_ANALYZE_EXPORT_COLUMNS)
        row.update(
            {
                **meta,
                "row_type": "warning",
                "warning": _cell(warning if isinstance(warning, str) else json.dumps(warning)),
            }
        )
        writer.writerow(row)
    return buf.getvalue()


async def export_document_analyze_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    upload: UploadFile,
    document_type: str = "receipt",
) -> str:
    """Stage 149 A1 — document analyze result CSV."""
    data = await ai_documents_svc.analyze_document(
        db,
        tenant_id,
        upload=upload,
        document_type=document_type,
    )
    return document_analyze_result_to_csv(data)
