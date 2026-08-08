"""Append-only audit logging with integrity hash chaining."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

GENESIS_HASH = "0" * 64


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


def serialize_audit(row: m.AuditLog) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "module": row.module or "system",
        "action": row.action,
        "entity": row.entity,
        "entity_id": row.entity_id,
        "details": row.details or {},
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "prev_hash": row.prev_hash,
        "integrity_hash": row.integrity_hash,
        "created_at": row.created_at,
    }


async def latest_integrity_hash(db: AsyncSession, tenant_id: str) -> str:
    row = (
        await db.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.integrity_hash.is_not(None),
            )
            .order_by(m.AuditLog.created_at.desc(), m.AuditLog.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return row.integrity_hash if row and row.integrity_hash else GENESIS_HASH


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
    created_at = datetime.utcnow()
    details = details or {}
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
    row = m.AuditLog(
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
    db.add(row)
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
        stmt = stmt.where(m.AuditLog.module == module)
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
    expected_prev = GENESIS_HASH
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
        expected = compute_integrity_hash(expected_prev, payload)
        if row.prev_hash != expected_prev or row.integrity_hash != expected:
            return {
                "valid": False,
                "checked": checked,
                "broken_at": row.id,
                "action": row.action,
                "created_at": row.created_at,
            }
        expected_prev = row.integrity_hash or expected_prev
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
                row.integrity_hash or "",
                json.dumps(row.details or {}, default=str),
            ]
        )
    return buf.getvalue()


def reject_mutation() -> None:
    raise HTTPException(
        status_code=405,
        detail="Audit logs are append-only and cannot be modified or deleted",
    )
