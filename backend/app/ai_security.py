"""AI Security Monitor — rule-based anomaly alerts (BR-21.10).

No LLM required. Scores login / access / mutation patterns from
tenant-scoped audit_logs, auth_sessions, users, and ai_queries.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import notifications as notifications_svc
from app import ai as ai_svc
from app.config import settings

# Detector kinds (stable API contract)
KIND_RAPID_FAILED_LOGINS = "rapid_failed_logins"
KIND_UNUSUAL_HOUR_LOGIN = "unusual_hour_login"
KIND_NEW_IP_LOGIN = "new_ip_login"
KIND_HTTP_WRITE_BURST = "http_write_burst"
KIND_AI_QUERY_BURST = "ai_query_burst"
KIND_ACCOUNT_LOCKED = "account_locked"
KIND_SUSPICIOUS_MUTATION_BURST = "suspicious_mutation_burst"

ALERT_THRESHOLD_DEFAULT = 60


def alert_threshold() -> int:
    return max(1, int(getattr(settings, "AI_SECURITY_ALERT_THRESHOLD", ALERT_THRESHOLD_DEFAULT) or ALERT_THRESHOLD_DEFAULT))


def monitor_enabled() -> bool:
    return bool(getattr(settings, "AI_SECURITY_MONITOR_ENABLED", True))


def _fingerprint(*parts: str) -> str:
    material = "|".join(parts).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def serialize_alert(row: m.AiSecurityAlert) -> dict[str, Any]:
    return {
        "id": row.id,
        "kind": row.kind,
        "risk_score": int(row.risk_score or 0),
        "user_id": row.user_id,
        "session_id": row.session_id,
        "title": row.title,
        "evidence": row.evidence or {},
        "status": row.status,
        "notified_at": row.notified_at,
        "created_at": row.created_at,
    }


async def list_alerts(
    db: AsyncSession,
    *,
    tenant_id: str,
    limit: int = 50,
    min_score: int | None = None,
) -> list[m.AiSecurityAlert]:
    lim = max(1, min(int(limit or 50), 200))
    stmt = select(m.AiSecurityAlert).where(m.AiSecurityAlert.tenant_id == tenant_id)
    if min_score is not None:
        stmt = stmt.where(m.AiSecurityAlert.risk_score >= int(min_score))
    rows = (
        await db.execute(stmt.order_by(m.AiSecurityAlert.created_at.desc()).limit(lim))
    ).scalars().all()
    return list(rows)


async def _upsert_alert(
    db: AsyncSession,
    *,
    tenant_id: str,
    kind: str,
    risk_score: int,
    fingerprint: str,
    title: str,
    user_id: str | None = None,
    session_id: str | None = None,
    evidence: dict | None = None,
) -> tuple[m.AiSecurityAlert, bool]:
    """Return (row, created). Updates score/evidence on existing fingerprint."""
    existing = (
        await db.execute(
            select(m.AiSecurityAlert).where(
                m.AiSecurityAlert.tenant_id == tenant_id,
                m.AiSecurityAlert.fingerprint == fingerprint,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.risk_score = max(int(existing.risk_score or 0), int(risk_score))
        existing.evidence = evidence or existing.evidence or {}
        existing.title = title
        existing.status = "open"
        await db.flush()
        return existing, False

    row = m.AiSecurityAlert(
        tenant_id=tenant_id,
        kind=kind,
        risk_score=int(risk_score),
        fingerprint=fingerprint,
        title=title,
        user_id=user_id,
        session_id=session_id,
        evidence=evidence or {},
        status="open",
    )
    db.add(row)
    await db.flush()
    return row, True


async def _notify_admins(
    db: AsyncSession,
    *,
    tenant_id: str,
    alert: m.AiSecurityAlert,
) -> None:
    if alert.risk_score < alert_threshold():
        return
    if alert.notified_at:
        return
    await notifications_svc.create_notification(
        db,
        tenant_id=tenant_id,
        title=f"Security alert: {alert.kind}",
        message=alert.title,
        category="security",
        user_id=None,  # fan-out to company_admin / super_admin
        entity_type="ai_security_alert",
        entity_id=alert.id,
    )
    alert.notified_at = datetime.utcnow()
    await db.flush()


async def _detect_rapid_failed_logins(
    db: AsyncSession, tenant_id: str, *, now: datetime, window_minutes: int = 15
) -> list[tuple[m.AiSecurityAlert, bool]]:
    since = now - timedelta(minutes=window_minutes)
    rows = (
        await db.execute(
            select(m.AuditLog.user_id, func.count())
            .where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.module == "auth",
                m.AuditLog.action == "login_failed",
                m.AuditLog.created_at >= since,
                m.AuditLog.user_id.is_not(None),
            )
            .group_by(m.AuditLog.user_id)
        )
    ).all()
    out: list[tuple[m.AiSecurityAlert, bool]] = []
    bucket = since.strftime("%Y%m%d%H")
    for user_id, count in rows:
        count = int(count or 0)
        if count < 3:
            continue
        score = 90 if count >= 5 else 70
        fp = _fingerprint(KIND_RAPID_FAILED_LOGINS, tenant_id, str(user_id), bucket)
        alert, created = await _upsert_alert(
            db,
            tenant_id=tenant_id,
            kind=KIND_RAPID_FAILED_LOGINS,
            risk_score=score,
            fingerprint=fp,
            title=f"{count} failed login attempts in {window_minutes} minutes",
            user_id=str(user_id),
            evidence={"failed_count": count, "window_minutes": window_minutes},
        )
        out.append((alert, created))
    return out


async def _detect_account_locked(
    db: AsyncSession, tenant_id: str, *, now: datetime
) -> list[tuple[m.AiSecurityAlert, bool]]:
    users = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == tenant_id,
                m.User.locked_until.is_not(None),
                m.User.locked_until > now,
            )
        )
    ).scalars().all()
    out: list[tuple[m.AiSecurityAlert, bool]] = []
    day = now.strftime("%Y%m%d")
    for user in users:
        fp = _fingerprint(KIND_ACCOUNT_LOCKED, tenant_id, user.id, day)
        alert, created = await _upsert_alert(
            db,
            tenant_id=tenant_id,
            kind=KIND_ACCOUNT_LOCKED,
            risk_score=85,
            fingerprint=fp,
            title=f"Account locked until {user.locked_until.isoformat()}Z",
            user_id=user.id,
            evidence={"locked_until": user.locked_until.isoformat()},
        )
        out.append((alert, created))
    return out


async def _detect_unusual_hour_and_new_ip(
    db: AsyncSession, tenant_id: str, *, now: datetime, lookback_hours: int = 24
) -> list[tuple[m.AiSecurityAlert, bool]]:
    since = now - timedelta(hours=lookback_hours)
    logins = (
        await db.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.module == "auth",
                m.AuditLog.action == "login",
                m.AuditLog.created_at >= since,
            )
            .order_by(m.AuditLog.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    out: list[tuple[m.AiSecurityAlert, bool]] = []
    for row in logins:
        if not row.user_id:
            continue
        hour = row.created_at.hour if row.created_at else now.hour
        # Unusual hour: 00:00–04:59 UTC
        if 0 <= hour < 5:
            # Only flag if user has prior daytime logins (baseline)
            prior = (
                await db.execute(
                    select(func.count())
                    .select_from(m.AuditLog)
                    .where(
                        m.AuditLog.tenant_id == tenant_id,
                        m.AuditLog.user_id == row.user_id,
                        m.AuditLog.module == "auth",
                        m.AuditLog.action == "login",
                        m.AuditLog.created_at < row.created_at,
                    )
                )
            ).scalar_one()
            if int(prior or 0) >= 2:
                fp = _fingerprint(
                    KIND_UNUSUAL_HOUR_LOGIN,
                    tenant_id,
                    row.user_id,
                    row.created_at.strftime("%Y%m%d%H"),
                )
                alert, created = await _upsert_alert(
                    db,
                    tenant_id=tenant_id,
                    kind=KIND_UNUSUAL_HOUR_LOGIN,
                    risk_score=55,
                    fingerprint=fp,
                    title=f"Login at unusual hour (UTC {hour:02d}:00)",
                    user_id=row.user_id,
                    evidence={"hour_utc": hour, "ip_address": row.ip_address},
                )
                out.append((alert, created))

        # New IP vs prior sessions
        ip = (row.ip_address or "").strip()
        if ip:
            known = (
                await db.execute(
                    select(func.count())
                    .select_from(m.AuthSession)
                    .where(
                        m.AuthSession.tenant_id == tenant_id,
                        m.AuthSession.user_id == row.user_id,
                        m.AuthSession.ip_address == ip,
                        m.AuthSession.created_at < row.created_at,
                    )
                )
            ).scalar_one()
            prior_sessions = (
                await db.execute(
                    select(func.count())
                    .select_from(m.AuthSession)
                    .where(
                        m.AuthSession.tenant_id == tenant_id,
                        m.AuthSession.user_id == row.user_id,
                        m.AuthSession.created_at < row.created_at,
                    )
                )
            ).scalar_one()
            if int(prior_sessions or 0) >= 1 and int(known or 0) == 0:
                fp = _fingerprint(
                    KIND_NEW_IP_LOGIN,
                    tenant_id,
                    row.user_id,
                    ip,
                    row.created_at.strftime("%Y%m%d"),
                )
                alert, created = await _upsert_alert(
                    db,
                    tenant_id=tenant_id,
                    kind=KIND_NEW_IP_LOGIN,
                    risk_score=65,
                    fingerprint=fp,
                    title="Login from new IP address",
                    user_id=row.user_id,
                    evidence={"ip_address": ip},
                )
                out.append((alert, created))
    return out


async def _detect_bursts(
    db: AsyncSession, tenant_id: str, *, now: datetime, window_minutes: int = 10
) -> list[tuple[m.AiSecurityAlert, bool]]:
    since = now - timedelta(minutes=window_minutes)
    out: list[tuple[m.AiSecurityAlert, bool]] = []
    bucket = since.strftime("%Y%m%d%H%M")[:11]  # ~10-min bucket

    http_rows = (
        await db.execute(
            select(m.AuditLog.user_id, func.count())
            .where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.action == "http_write",
                m.AuditLog.created_at >= since,
                m.AuditLog.user_id.is_not(None),
            )
            .group_by(m.AuditLog.user_id)
        )
    ).all()
    for user_id, count in http_rows:
        count = int(count or 0)
        if count < 40:
            continue
        fp = _fingerprint(KIND_HTTP_WRITE_BURST, tenant_id, str(user_id), bucket)
        alert, created = await _upsert_alert(
            db,
            tenant_id=tenant_id,
            kind=KIND_HTTP_WRITE_BURST,
            risk_score=70 if count >= 80 else 60,
            fingerprint=fp,
            title=f"{count} HTTP write mutations in {window_minutes} minutes",
            user_id=str(user_id),
            evidence={"write_count": count, "window_minutes": window_minutes},
        )
        out.append((alert, created))

    # Suspicious mutation burst: cancels / restores / deletes
    cancel_rows = (
        await db.execute(
            select(m.AuditLog.user_id, func.count())
            .where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.created_at >= since,
                m.AuditLog.user_id.is_not(None),
                or_(
                    m.AuditLog.action.ilike("%cancel%"),
                    m.AuditLog.action.ilike("%restore%"),
                    m.AuditLog.action.ilike("%delete%"),
                ),
            )
            .group_by(m.AuditLog.user_id)
        )
    ).all()
    for user_id, count in cancel_rows:
        count = int(count or 0)
        if count < 5:
            continue
        fp = _fingerprint(KIND_SUSPICIOUS_MUTATION_BURST, tenant_id, str(user_id), bucket)
        alert, created = await _upsert_alert(
            db,
            tenant_id=tenant_id,
            kind=KIND_SUSPICIOUS_MUTATION_BURST,
            risk_score=75,
            fingerprint=fp,
            title=f"{count} cancel/restore/delete actions in {window_minutes} minutes",
            user_id=str(user_id),
            evidence={"mutation_count": count, "window_minutes": window_minutes},
        )
        out.append((alert, created))

    ai_rows = (
        await db.execute(
            select(m.AiQuery.user_id, func.count())
            .where(
                m.AiQuery.tenant_id == tenant_id,
                m.AiQuery.created_at >= since,
                m.AiQuery.user_id.is_not(None),
            )
            .group_by(m.AiQuery.user_id)
        )
    ).all()
    for user_id, count in ai_rows:
        count = int(count or 0)
        if count < 20:
            continue
        fp = _fingerprint(KIND_AI_QUERY_BURST, tenant_id, str(user_id), bucket)
        alert, created = await _upsert_alert(
            db,
            tenant_id=tenant_id,
            kind=KIND_AI_QUERY_BURST,
            risk_score=55,
            fingerprint=fp,
            title=f"{count} AI queries in {window_minutes} minutes",
            user_id=str(user_id),
            evidence={"query_count": count, "window_minutes": window_minutes},
        )
        out.append((alert, created))

    return out


async def scan_tenant(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_user_id: str | None = None,
    notify: bool = True,
) -> dict[str, Any]:
    """Run all detectors for one tenant. Returns summary + new alerts."""
    if not monitor_enabled():
        return {
            "enabled": False,
            "created": 0,
            "updated": 0,
            "notified": 0,
            "alerts": [],
        }

    now = datetime.utcnow()
    collected: list[tuple[m.AiSecurityAlert, bool]] = []
    collected.extend(await _detect_rapid_failed_logins(db, tenant_id, now=now))
    collected.extend(await _detect_account_locked(db, tenant_id, now=now))
    collected.extend(await _detect_unusual_hour_and_new_ip(db, tenant_id, now=now))
    collected.extend(await _detect_bursts(db, tenant_id, now=now))

    created = sum(1 for _, c in collected if c)
    updated = sum(1 for _, c in collected if not c)
    notified = 0
    if notify:
        seen: set[str] = set()
        for alert, _ in collected:
            if alert.id in seen:
                continue
            seen.add(alert.id)
            before = alert.notified_at
            await _notify_admins(db, tenant_id=tenant_id, alert=alert)
            if alert.notified_at and before != alert.notified_at:
                notified += 1

    await ai_svc.record_query(
        db,
        tenant_id=tenant_id,
        user_id=actor_user_id,
        endpoint="security_scan",
        status="ok",
        details={
            "created": created,
            "updated": updated,
            "notified": notified,
            "threshold": alert_threshold(),
        },
    )

    # Deduplicate alert objects by id for response
    by_id: dict[str, m.AiSecurityAlert] = {}
    for alert, _ in collected:
        by_id[alert.id] = alert

    return {
        "enabled": True,
        "created": created,
        "updated": updated,
        "notified": notified,
        "threshold": alert_threshold(),
        "alerts": [serialize_alert(a) for a in by_id.values()],
    }
