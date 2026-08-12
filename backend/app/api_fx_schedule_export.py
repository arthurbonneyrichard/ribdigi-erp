"""CSV export for API keys, FX rates, and report schedules (Stage 127). Secrets excluded."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app import api_keys as api_keys_svc
from app import fx as fx_svc
from app import report_schedules as report_schedules_svc

API_KEY_EXPORT_COLUMNS = [
    "name",
    "key_prefix",
    "status",
    "request_count",
    "last_used_at",
    "expires_at",
    "revoked_at",
    "created_at",
]

FX_RATE_EXPORT_COLUMNS = [
    "base_currency",
    "currency_code",
    "rate_to_base",
    "source",
    "provider_fetched_at",
    "updated_at",
]

SCHEDULE_EXPORT_COLUMNS = [
    "name",
    "report_type",
    "format",
    "frequency",
    "weekday",
    "hour_utc",
    "recipients",
    "enabled",
    "last_run_at",
    "last_error",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


async def export_api_keys_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    active_only: bool = False,
) -> str:
    rows = await api_keys_svc.list_keys(
        db, tenant_id, status=status, active_only=active_only
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=API_KEY_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = api_keys_svc.serialize_key(row)
        writer.writerow(
            {
                "name": _cell(data.get("name")),
                "key_prefix": _cell(data.get("key_prefix")),
                "status": _cell(data.get("status")),
                "request_count": _cell(data.get("request_count")),
                "last_used_at": _cell(data.get("last_used_at")),
                "expires_at": _cell(data.get("expires_at")),
                "revoked_at": _cell(data.get("revoked_at")),
                "created_at": _cell(data.get("created_at")),
            }
        )
    return buf.getvalue()


async def export_exchange_rates_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> str:
    base = await fx_svc.get_base_currency(db, tenant_id)
    rows = await fx_svc.list_rates(db, tenant_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FX_RATE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = fx_svc.serialize_rate(row)
        writer.writerow(
            {
                "base_currency": _cell(base),
                "currency_code": _cell(data.get("currency_code")),
                "rate_to_base": _cell(float(data.get("rate_to_base") or 0)),
                "source": _cell(data.get("source")),
                "provider_fetched_at": _cell(data.get("provider_fetched_at")),
                "updated_at": _cell(data.get("updated_at")),
            }
        )
    return buf.getvalue()


async def export_report_schedules_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    enabled: bool | None = None,
) -> str:
    rows = await report_schedules_svc.list_schedules(
        db, tenant_id, enabled=enabled
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SCHEDULE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = report_schedules_svc.serialize_schedule(row)
        writer.writerow(
            {
                "name": _cell(data.get("name")),
                "report_type": _cell(data.get("report_type")),
                "format": _cell(data.get("format")),
                "frequency": _cell(data.get("frequency")),
                "weekday": _cell(data.get("weekday")),
                "hour_utc": _cell(data.get("hour_utc")),
                "recipients": _cell(data.get("recipients") or []),
                "enabled": _cell(bool(data.get("enabled"))),
                "last_run_at": _cell(data.get("last_run_at")),
                "last_error": _cell(data.get("last_error")),
            }
        )
    return buf.getvalue()
