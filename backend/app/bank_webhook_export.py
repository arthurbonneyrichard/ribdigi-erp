"""CSV export for bank connections and webhooks (Stage 126 X1) and bank-feed settings (Stage 156 F1). Secrets excluded."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import webhooks as webhooks_svc

BANK_CONNECTION_EXPORT_COLUMNS = [
    "display_name",
    "provider",
    "account_id",
    "external_account_id",
    "feed_url",
    "auto_sync",
    "auto_match_after_sync",
    "sync_lookback_days",
    "is_active",
    "last_sync_status",
    "last_synced_at",
]

BANK_FEED_SETTINGS_EXPORT_COLUMNS = [
    "sync_enabled",
    "providers",
    "timeout_seconds",
    "celery_interval_minutes",
]

WEBHOOK_EXPORT_COLUMNS = [
    "url",
    "events",
    "description",
    "is_active",
    "failure_count",
    "last_status_code",
    "last_delivery_at",
]

WEBHOOK_DELIVERY_EXPORT_COLUMNS = [
    "id",
    "webhook_id",
    "event",
    "status",
    "attempt_count",
    "response_status",
    "error",
    "next_retry_at",
    "created_at",
    "delivered_at",
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
        return f"{value:.4f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


def _apply_active_filter(stmt, column, *, is_active: bool | None, active_only: bool):
    if is_active is not None:
        return stmt.where(column.is_(bool(is_active)))
    if active_only:
        return stmt.where(column.is_(True))
    return stmt


async def export_bank_connections_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    stmt = select(m.BankAccountConnection).where(
        m.BankAccountConnection.tenant_id == tenant_id
    )
    stmt = _apply_active_filter(
        stmt,
        m.BankAccountConnection.is_active,
        is_active=is_active,
        active_only=active_only,
    )
    rows = (
        await db.execute(stmt.order_by(m.BankAccountConnection.created_at.desc()))
    ).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=BANK_CONNECTION_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "display_name": _cell(row.display_name),
                "provider": _cell(row.provider),
                "account_id": _cell(row.account_id),
                "external_account_id": _cell(row.external_account_id),
                "feed_url": _cell(row.feed_url),
                "auto_sync": _cell(bool(row.auto_sync)),
                "auto_match_after_sync": _cell(bool(row.auto_match_after_sync)),
                "sync_lookback_days": _cell(int(row.sync_lookback_days or 30)),
                "is_active": _cell(bool(row.is_active)),
                "last_sync_status": _cell(row.last_sync_status),
                "last_synced_at": _cell(row.last_synced_at),
            }
        )
    return buf.getvalue()


def export_bank_feed_settings_csv() -> str:
    """Stage 156 F1 — secret-free bank-feed capability settings (no tokens/credentials)."""
    from app import bank_connectors as bank_connectors_svc

    payload = bank_connectors_svc.settings_payload()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=BANK_FEED_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "sync_enabled": _cell(bool(payload.get("sync_enabled"))),
            "providers": _cell(
                json.dumps(payload.get("providers") or [], separators=(",", ":"))
            ),
            "timeout_seconds": _cell(payload.get("timeout_seconds")),
            "celery_interval_minutes": _cell(payload.get("celery_interval_minutes")),
        }
    )
    return buf.getvalue()


async def export_webhooks_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    is_active: bool | None = None,
    active_only: bool = False,
) -> str:
    stmt = select(m.WebhookEndpoint).where(m.WebhookEndpoint.tenant_id == tenant_id)
    stmt = _apply_active_filter(
        stmt, m.WebhookEndpoint.is_active, is_active=is_active, active_only=active_only
    )
    rows = (
        await db.execute(stmt.order_by(m.WebhookEndpoint.created_at.desc()))
    ).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=WEBHOOK_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "url": _cell(row.url),
                "events": _cell(row.events or []),
                "description": _cell(row.description),
                "is_active": _cell(bool(row.is_active)),
                "failure_count": _cell(int(row.failure_count or 0)),
                "last_status_code": _cell(row.last_status_code),
                "last_delivery_at": _cell(row.last_delivery_at),
            }
        )
    return buf.getvalue()


async def export_webhook_deliveries_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    webhook_id: str | None = None,
    status: str | None = None,
) -> str:
    """Stage 144 W1 — delivery attempt CSV; payload / signing secrets never included."""
    rows = await webhooks_svc.list_deliveries(
        db, tenant_id, webhook_id=webhook_id, status=status
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=WEBHOOK_DELIVERY_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = webhooks_svc.serialize_delivery(row)
        writer.writerow({k: _cell(data.get(k)) for k in WEBHOOK_DELIVERY_EXPORT_COLUMNS})
    return buf.getvalue()
