"""CSV export for inventory FEFO settings and audit cold archives (Stage 144). Secrets excluded."""

from __future__ import annotations

import csv
import io

from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import tenants as tenants_svc
from app.session_passkey_doc_export import _cell

FEFO_SETTINGS_EXPORT_COLUMNS = [
    "fefo_strict_warehouse",
]

AUDIT_ARCHIVE_EXPORT_COLUMNS = [
    "id",
    "storage_key",
    "sha256",
    "event_count",
    "from_created_at",
    "to_created_at",
    "byte_size",
    "created_by",
    "created_at",
]


async def export_fefo_settings_csv(db: AsyncSession, *, tenant_id: str) -> str:
    """Stage 144 F1 — inventory FEFO policy CSV (single-row settings)."""
    tenant = await tenants_svc.get_tenant(db, tenant_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=FEFO_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "fefo_strict_warehouse": _cell(
                bool(getattr(tenant, "fefo_strict_warehouse", False))
            ),
        }
    )
    return buf.getvalue()


async def export_audit_archives_csv(db: AsyncSession, *, tenant_id: str) -> str:
    """Stage 144 A1 — cold audit archive manifest CSV (no archive blob bytes)."""
    rows = await audit_svc.list_cold_archives(db, tenant_id=tenant_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=AUDIT_ARCHIVE_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = audit_svc.serialize_cold_archive(row)
        writer.writerow({k: _cell(data.get(k)) for k in AUDIT_ARCHIVE_EXPORT_COLUMNS})
    return buf.getvalue()
