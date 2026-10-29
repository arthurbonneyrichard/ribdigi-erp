"""Append-only audit logging with integrity hash chaining."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import schema_compat
from app.models import uid

GENESIS_HASH = "0" * 64

# Modules accepted on GET /audit-logs?module= (record_event + middleware segments + system).
AUDIT_MODULES = frozenset(
    {
        "accounting",
        "ai",
        "audit",
        "auth",
        "backup",
        "company",
        "credit",
        "dashboard",
        "expenses",
        "billing",
        "fmcg",
        "hotel",
        "restaurant",
        "inventory",
        "notifications",
        "onboarding",
        "platform_staff",
        "pos",
        "purchasing",
        "reports",
        "sales",
        "security",
        "settings",
        "stores",
        "system",
        "tax",
        "tenants",
        "users",
        "webhooks",
        "printers",
    }
)


def canonical_payload(
    *,
    tenant_id: str,
    user_id: str | None,
    module: str,
    action: str,
    entity: str,
    entity_id: str | None,
    details: dict,
    created_at: datetime,
) -> str:
    body = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "module": module,
        "action": action,
        "entity": entity,
        "entity_id": entity_id,
        "details": details or {},
        "created_at": created_at.isoformat(),
    }
    return json.dumps(body, sort_keys=True, default=str)


def compute_integrity_hash(prev_hash: str, payload: str) -> str:
    material = f"{prev_hash}|{payload}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


_SECRET_DETAIL_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "secret",
        "token",
        "refresh_token",
        "access_token",
        "api_key",
        "authorization",
        "totp_secret",
        "totp_secret_enc",
        "backup_codes",
        "smtp_password",
        "smtp_password_enc",
    }
)


def redact_audit_details(details: dict | None) -> dict:
    """Never return passwords or secrets on the tenant audit API."""
    out: dict = {}
    for key, value in (details or {}).items():
        lk = str(key).lower()
        if lk in _SECRET_DETAIL_KEYS or "password" in lk or lk.endswith("_secret") or lk.endswith("_token"):
            out[key] = "[redacted]"
        elif isinstance(value, dict):
            out[key] = redact_audit_details(value)
        else:
            out[key] = value
    return out


def reject_mutation() -> None:
    """Audit logs are append-only. Tenants cannot edit or erase events."""
    raise HTTPException(
        status_code=403,
        detail="Audit logs cannot be edited or deleted",
    )


def serialize_audit(row: m.AuditLog) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "module": row.module or "system",
        "action": row.action,
        "entity": row.entity,
        "entity_id": row.entity_id,
        "details": redact_audit_details(row.details if isinstance(row.details, dict) else {}),
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "archived_at": getattr(row, "archived_at", None),
        "created_at": row.created_at,
    }


async def latest_integrity_hash(db: AsyncSession, tenant_id: str) -> str:
    try:
        cols = await schema_compat.table_column_names(db, "audit_logs")
        if "integrity_hash" not in cols or "tenant_id" not in cols:
            return GENESIS_HASH
        order = "created_at DESC" if "created_at" in cols else "id DESC"
        result = await db.execute(
            text(
                f"SELECT integrity_hash FROM audit_logs "
                f"WHERE tenant_id = :tid AND integrity_hash IS NOT NULL "
                f"ORDER BY {order} LIMIT 1"
            ),
            {"tid": tenant_id},
        )
        value = result.scalar()
        return str(value) if value else GENESIS_HASH
    except Exception:
        return GENESIS_HASH


async def record_event(
    db: AsyncSession,
    *,
    tenant_id: str,
    action: str,
    entity: str,
    user_id: str | None = None,
    entity_id: str | None = None,
    details: dict | None = None,
    module: str = "system",
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> m.AuditLog:
    details = details or {}
    # One writer per company at a time: two requests appending together would both chain to the
    # same previous hash and fork the log, so verify_chain would report a break. The lock is
    # transaction-scoped (released on commit/rollback). SQLite tests are single-writer already.
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"audit-chain:{tenant_id}"})
    created_at = datetime.utcnow()
    prev = await latest_integrity_hash(db, tenant_id)
    payload = canonical_payload(
        tenant_id=tenant_id,
        user_id=user_id,
        module=module,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
        created_at=created_at,
    )
    integrity = compute_integrity_hash(prev, payload)
    row_id = uid()
    row = m.AuditLog(
        id=row_id,
        tenant_id=tenant_id,
        user_id=user_id,
        module=module,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        prev_hash=prev,
        integrity_hash=integrity,
        created_at=created_at,
    )
    await schema_compat.insert_matching_row(
        db,
        "audit_logs",
        {
            "id": row_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "module": module,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "details": details,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "prev_hash": prev,
            "integrity_hash": integrity,
            "created_at": created_at,
            "company_id": None,
        },
    )
    await db.flush()
    return row


async def query_logs(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None = None,
    module: str | None = None,
    action: str | None = None,
    entity: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 200,
) -> list[m.AuditLog]:
    stmt = select(m.AuditLog).where(m.AuditLog.tenant_id == tenant_id)
    if user_id:
        stmt = stmt.where(m.AuditLog.user_id == user_id)
    if module:
        # Schema AuditModuleValue rejects blank/unknown → 422; keep allow-list defense-in-depth.
        mod = module.strip().lower()
        if mod and mod not in AUDIT_MODULES:
            raise HTTPException(
                status_code=400,
                detail=f"module must be one of: {', '.join(sorted(AUDIT_MODULES))}",
            )
        if mod:
            stmt = stmt.where(m.AuditLog.module == mod)
    if action:
        stmt = stmt.where(m.AuditLog.action == action)
    if entity:
        stmt = stmt.where(m.AuditLog.entity == entity)
    if from_date:
        stmt = stmt.where(m.AuditLog.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.AuditLog.created_at <= to_date)
    stmt = stmt.order_by(m.AuditLog.created_at.desc()).limit(min(limit, 1000))
    return (await db.execute(stmt)).scalars().all()


async def verify_chain(db: AsyncSession, tenant_id: str) -> dict:
    rows = (
        await db.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.integrity_hash.is_not(None),
            )
            .order_by(m.AuditLog.created_at.asc(), m.AuditLog.id.asc())
        )
    ).scalars().all()
    # Each entry must hash correctly from its own content and link to an earlier entry (or genesis).
    # An edited entry fails its hash; a deleted entry leaves its successor pointing at a missing hash.
    # Links are checked against every earlier entry, not only the one just before: before appends were
    # serialised, two entries written at the same moment could share a parent (a fork), which is not tampering.
    seen = {GENESIS_HASH}
    checked = 0
    for row in rows:
        payload = canonical_payload(
            tenant_id=row.tenant_id,
            user_id=row.user_id,
            module=row.module or "system",
            action=row.action,
            entity=row.entity,
            entity_id=row.entity_id,
            details=row.details or {},
            created_at=row.created_at,
        )
        prev = row.prev_hash or ""
        if prev not in seen or row.integrity_hash != compute_integrity_hash(prev, payload):
            return {
                "valid": False,
                "checked": checked,
                "broken_at": row.id,
                "action": row.action,
                "created_at": row.created_at,
            }
        seen.add(row.integrity_hash)
        checked += 1
    return {"valid": True, "checked": checked, "broken_at": None}


def to_csv(rows: list[m.AuditLog]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "created_at",
            "user_id",
            "module",
            "action",
            "entity",
            "entity_id",
            "ip_address",
            "integrity_hash",
            "details",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.created_at.isoformat() if row.created_at else "",
                row.user_id or "",
                row.module or "",
                row.action,
                row.entity,
                row.entity_id or "",
                row.ip_address or "",
                "",
                json.dumps(redact_audit_details(row.details if isinstance(row.details, dict) else {}), default=str),
            ]
        )
    return buf.getvalue()



def retention_policy() -> dict:
    """BR-17.2 retention / cold-archive policy."""
    from app.config import settings

    years = max(7, int(getattr(settings, "AUDIT_RETENTION_YEARS", 7) or 7))
    hot_days = max(1, int(getattr(settings, "AUDIT_COLD_ARCHIVE_AFTER_DAYS", 365) or 365))
    return {
        "retention_years": years,
        "retention_days": years * 365,
        "cold_archive_after_days": hot_days,
        "purge_allowed": False,
        "notes": (
            "Financial/audit records are retained at least 7 years. "
            "Cold archive writes a checksummed JSONL copy to object storage; "
            "hot rows are marked archived_at and never deleted."
        ),
    }


def serialize_cold_archive(row: m.AuditColdArchive) -> dict:
    return {
        "id": row.id,
        "storage_key": row.storage_key,
        "sha256": row.sha256,
        "event_count": row.event_count,
        "from_created_at": row.from_created_at,
        "to_created_at": row.to_created_at,
        "byte_size": row.byte_size,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


async def list_cold_archives(
    db: AsyncSession, *, tenant_id: str, limit: int = 50
) -> list[m.AuditColdArchive]:
    return list(
        (
            await db.execute(
                select(m.AuditColdArchive)
                .where(m.AuditColdArchive.tenant_id == tenant_id)
                .order_by(m.AuditColdArchive.created_at.desc())
                .limit(min(limit, 200))
            )
        )
        .scalars()
        .all()
    )


async def archive_cold_logs(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None = None,
    older_than_days: int | None = None,
    limit: int = 5000,
) -> dict:
    """Export aged, not-yet-archived audit rows to cold storage and mark them.

    Does not delete rows (7-year retention). Returns archive manifest summary.
    """
    import hashlib
    from datetime import timedelta

    from app import storage as storage_svc

    policy = retention_policy()
    days = older_than_days if older_than_days is not None else policy["cold_archive_after_days"]
    days = max(1, int(days))
    cutoff = datetime.utcnow() - timedelta(days=days)

    rows = (
        await db.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.created_at < cutoff,
                m.AuditLog.archived_at.is_(None),
            )
            .order_by(m.AuditLog.created_at.asc(), m.AuditLog.id.asc())
            .limit(min(max(limit, 1), 20000))
        )
    ).scalars().all()
    if not rows:
        return {
            "archived": 0,
            "archive_id": None,
            "storage_key": None,
            "cutoff": cutoff,
            "policy": policy,
        }

    lines: list[str] = []
    for row in rows:
        lines.append(
            json.dumps(
                {
                    "id": row.id,
                    "tenant_id": row.tenant_id,
                    "user_id": row.user_id,
                    "module": row.module,
                    "action": row.action,
                    "entity": row.entity,
                    "entity_id": row.entity_id,
                    "details": row.details or {},
                    "ip_address": row.ip_address,
                    "user_agent": row.user_agent,
                    "prev_hash": row.prev_hash,
                    "integrity_hash": row.integrity_hash,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                },
                sort_keys=True,
                default=str,
            )
        )
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    key = f"{tenant_id}/audit-cold/{stamp}-{digest[:12]}.jsonl"
    storage_svc._put_bytes(key, payload, "application/x-ndjson")

    now = datetime.utcnow()
    archive = m.AuditColdArchive(
        tenant_id=tenant_id,
        storage_key=key,
        sha256=digest,
        event_count=len(rows),
        from_created_at=rows[0].created_at,
        to_created_at=rows[-1].created_at,
        byte_size=len(payload),
        created_by=user_id,
        created_at=now,
    )
    db.add(archive)
    for row in rows:
        row.archived_at = now
    await db.flush()

    await record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="audit",
        action="audit_cold_archived",
        entity="audit_cold_archive",
        entity_id=archive.id,
        details={
            "event_count": len(rows),
            "storage_key": key,
            "sha256": digest,
            "cold_archive_after_days": days,
            "retention_years": policy["retention_years"],
        },
    )
    return {
        "archived": len(rows),
        "archive_id": archive.id,
        "storage_key": key,
        "sha256": digest,
        "byte_size": len(payload),
        "cutoff": cutoff,
        "policy": policy,
        "from_created_at": rows[0].created_at,
        "to_created_at": rows[-1].created_at,
    }
