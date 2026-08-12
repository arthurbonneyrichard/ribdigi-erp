"""CSV export for storage, notification preferences, and backup schedule settings (Stage 140). Secrets excluded."""

from __future__ import annotations

import csv
import io

from sqlalchemy.ext.asyncio import AsyncSession

from app import backup as backup_svc
from app import notifications as notifications_svc
from app import storage as storage_svc
from app.session_passkey_doc_export import _cell

STORAGE_SETTINGS_EXPORT_COLUMNS = [
    "backend",
    "media_dir",
    "bucket",
    "endpoint",
    "region",
]

NOTIFICATION_PREFS_EXPORT_COLUMNS = [
    "category",
    "dashboard",
    "email",
    "sms",
]

BACKUP_SETTINGS_EXPORT_COLUMNS = [
    "enabled",
    "frequency",
    "retention_count",
    "hour_utc",
    "last_run_at",
    "updated_at",
]


def export_storage_settings_csv() -> str:
    """Stage 140 S1 — storage backend status CSV; never include S3 access/secret keys."""
    data = storage_svc.storage_status()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=STORAGE_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(data.get(k)) for k in STORAGE_SETTINGS_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_notification_preferences_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
) -> str:
    """Stage 140 N1 — per-category channel preferences for the calling user."""
    prefs = await notifications_svc.get_preferences(db, tenant_id, user_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=NOTIFICATION_PREFS_EXPORT_COLUMNS)
    writer.writeheader()
    for category in sorted(prefs.keys()):
        channels = prefs.get(category) or {}
        writer.writerow(
            {
                "category": _cell(category),
                "dashboard": _cell(bool(channels.get("dashboard"))),
                "email": _cell(bool(channels.get("email"))),
                "sms": _cell(bool(channels.get("sms"))),
            }
        )
    return buf.getvalue()


async def export_backup_settings_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
) -> str:
    """Stage 140 B1 — backup schedule settings CSV; never include archive bytes or credentials."""
    row = await backup_svc.get_or_create_settings(db, tenant_id)
    data = backup_svc.serialize_settings(row)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=BACKUP_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(data.get(k)) for k in BACKUP_SETTINGS_EXPORT_COLUMNS})
    return buf.getvalue()
