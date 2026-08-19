"""CSV export for tenant admin sessions, notifications, and backup jobs (Stage 129). Secrets excluded."""

from __future__ import annotations

import csv
import io

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import notifications as notifications_svc
from app import backup as backup_svc
from app.session_passkey_doc_export import session_status, _cell

TENANT_SESSION_EXPORT_COLUMNS = [
    "id",
    "user_email",
    "user_name",
    "status",
    "ip_address",
    "user_agent",
    "expires_at",
    "revoked_at",
    "created_at",
]

NOTIFICATION_EXPORT_COLUMNS = [
    "created_at",
    "status",
    "group",
    "category",
    "title",
    "message",
    "entity_type",
    "entity_id",
]

BACKUP_EXPORT_COLUMNS = [
    "id",
    "status",
    "filename",
    "size_bytes",
    "checksum_sha256",
    "encrypted",
    "offsite_uploaded",
    "offsite_uri",
    "notes",
    "error_message",
    "created_by",
    "created_at",
]


async def list_tenant_sessions(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    active_only: bool = False,
    user_id: str | None = None,
) -> list[m.AuthSession]:
    """Tenant-wide session inventory for company_admin / super_admin."""
    q = select(m.AuthSession).where(m.AuthSession.tenant_id == tenant_id)
    if user_id:
        q = q.where(m.AuthSession.user_id == user_id)
    status_n = (status or "").strip().lower() or None
    if status_n == "revoked":
        q = q.where(m.AuthSession.revoked_at.is_not(None))
    elif status_n == "active" or active_only:
        q = q.where(m.AuthSession.revoked_at.is_(None))
    elif status_n == "all":
        pass
    else:
        q = q.where(m.AuthSession.revoked_at.is_(None))
    q = q.order_by(m.AuthSession.created_at.desc()).limit(500)
    return list((await db.execute(q)).scalars().all())


async def user_map(db: AsyncSession, tenant_id: str, user_ids: set[str]) -> dict[str, m.User]:
    if not user_ids:
        return {}
    rows = (
        await db.execute(
            select(m.User).where(m.User.tenant_id == tenant_id, m.User.id.in_(list(user_ids)))
        )
    ).scalars().all()
    return {u.id: u for u in rows}


def serialize_tenant_session(row: m.AuthSession, user: m.User | None = None) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_email": user.email if user else None,
        "user_name": user.full_name if user else None,
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "expires_at": row.expires_at,
        "revoked_at": row.revoked_at,
        "created_at": row.created_at,
        "status": session_status(row),
    }


async def export_tenant_sessions_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    active_only: bool = False,
    user_id: str | None = None,
) -> str:
    rows = await list_tenant_sessions(
        db,
        tenant_id=tenant_id,
        status=status,
        active_only=active_only,
        user_id=user_id,
    )
    users = await user_map(db, tenant_id, {r.user_id for r in rows})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=TENANT_SESSION_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = serialize_tenant_session(row, users.get(row.user_id))
        writer.writerow(
            {
                "id": _cell(data.get("id")),
                "user_email": _cell(data.get("user_email")),
                "user_name": _cell(data.get("user_name")),
                "status": _cell(data.get("status")),
                "ip_address": _cell(data.get("ip_address")),
                "user_agent": _cell(data.get("user_agent")),
                "expires_at": _cell(data.get("expires_at")),
                "revoked_at": _cell(data.get("revoked_at")),
                "created_at": _cell(data.get("created_at")),
            }
        )
    return buf.getvalue()


async def export_notifications_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    status: str | None = None,
    category: str | None = None,
    group: str | None = None,
    company_id: str | None = None,
) -> str:
    status_n = (status or "").strip().lower() or None
    if status_n == "all":
        status_n = None
    rows = await notifications_svc.list_notifications(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        status=status_n,
        category=category,
        group=group,
        limit=500,
        company_id=company_id,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=NOTIFICATION_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = notifications_svc.serialize_notification(row)
        writer.writerow(
            {
                "created_at": _cell(data.get("created_at")),
                "status": _cell(data.get("status")),
                "group": _cell(data.get("group")),
                "category": _cell(data.get("category")),
                "title": _cell(data.get("title")),
                "message": _cell(data.get("message")),
                "entity_type": _cell(data.get("entity_type")),
                "entity_id": _cell(data.get("entity_id")),
            }
        )
    return buf.getvalue()


async def list_backup_jobs(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
    limit: int = 50,
) -> list[m.BackupJob]:
    q = select(m.BackupJob).where(m.BackupJob.tenant_id == tenant_id)
    status_n = (status or "").strip().lower() or None
    if status_n:
        q = q.where(m.BackupJob.status == status_n)
    q = q.order_by(m.BackupJob.created_at.desc()).limit(min(max(limit, 1), 200))
    return list((await db.execute(q)).scalars().all())


async def export_backup_jobs_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    status: str | None = None,
) -> str:
    rows = await list_backup_jobs(db, tenant_id=tenant_id, status=status, limit=200)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=BACKUP_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = backup_svc.serialize_job(row)
        writer.writerow(
            {
                "id": _cell(data.get("id")),
                "status": _cell(data.get("status")),
                "filename": _cell(data.get("filename")),
                "size_bytes": _cell(data.get("size_bytes")),
                "checksum_sha256": _cell(data.get("checksum_sha256")),
                "encrypted": _cell(data.get("encrypted")),
                "offsite_uploaded": _cell(data.get("offsite_uploaded")),
                "offsite_uri": _cell(data.get("offsite_uri")),
                "notes": _cell(data.get("notes")),
                "error_message": _cell(data.get("error_message")),
                "created_by": _cell(data.get("created_by")),
                "created_at": _cell(data.get("created_at")),
            }
        )
    return buf.getvalue()
