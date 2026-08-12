"""CSV export for AI security alerts, report templates, business insights (Stage 145),
and inventory low-stock / forecast / dead-stock predictions (Stage 146)."""

from __future__ import annotations

import csv
import io
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app import ai_insights as ai_insights_svc
from app import ai_inventory as ai_inventory_svc
from app import ai_reports as ai_reports_svc
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
