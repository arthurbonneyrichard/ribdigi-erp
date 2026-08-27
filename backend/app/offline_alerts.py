"""Tenant offline owner alerts (§13–38 follow-through).

In-app + optional security-email notify for critical alerts. Push delivery and
Offline Complete remain deferred — do not claim Completes.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import offline_devices as offline_devices_svc
from app.offline_auth_envelope import envelope_from_device
from app.notifications import create_notification

EXPIRING_SOON_HOURS = 24
SYNC_BACKLOG_THRESHOLD = 10


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "warning": 1, "info": 2}.get(severity, 3)


async def _pending_push_counts_by_device(
    db: AsyncSession, tenant_id: str
) -> dict[str | None, dict[str, int]]:
    rows = (
        await db.execute(
            select(
                m.SyncQueueItem.device_id,
                m.SyncQueueItem.status,
                func.count(),
            )
            .where(
                m.SyncQueueItem.tenant_id == tenant_id,
                m.SyncQueueItem.direction == "push",
                m.SyncQueueItem.status.in_(["pending", "failed"]),
            )
            .group_by(m.SyncQueueItem.device_id, m.SyncQueueItem.status)
        )
    ).all()
    out: dict[str | None, dict[str, int]] = {}
    for device_id, status, count in rows:
        bucket = out.setdefault(device_id, {"pending": 0, "failed": 0})
        bucket[str(status)] = int(count or 0)
    return out


async def collect_offline_alerts(db: AsyncSession, tenant_id: str) -> dict[str, Any]:
    """Build tenant-scoped offline alerts for owners/admins."""
    now = datetime.utcnow()
    expiring_cutoff = now + timedelta(hours=EXPIRING_SOON_HOURS)

    devices = await offline_devices_svc.list_devices(db, tenant_id, active_only=True)
    push_by_device = await _pending_push_counts_by_device(db, tenant_id)

    open_conflicts = int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.SyncConflict)
                .where(
                    m.SyncConflict.tenant_id == tenant_id,
                    m.SyncConflict.status == "open",
                )
            )
        ).scalar_one()
        or 0
    )

    alerts: list[dict[str, Any]] = []

    for device in devices:
        envelope = envelope_from_device(device)
        until_raw = envelope.get("offline_valid_until") if envelope else None
        until: datetime | None = None
        if until_raw:
            text = str(until_raw).strip()
            if text.endswith("Z"):
                text = text[:-1]
            try:
                until = datetime.fromisoformat(text)
            except ValueError:
                until = device.offline_authorized_until

        if envelope is None:
            alerts.append(
                {
                    "code": "OFFLINE_DEVICE_NEVER_BOUND",
                    "severity": "info",
                    "device_id": device.id,
                    "device_name": device.name,
                    "message": (
                        f"Device “{device.name}” is registered but has no offline auth envelope. "
                        "Bind online before relying on offline POS."
                    ),
                }
            )
        elif until is not None:
            if until <= now:
                alerts.append(
                    {
                        "code": "OFFLINE_ENVELOPE_EXPIRED",
                        "severity": "critical",
                        "device_id": device.id,
                        "device_name": device.name,
                        "offline_valid_until": until_raw,
                        "message": (
                            f"Offline authorization expired for “{device.name}”. "
                            "Renew online via bind before new offline sales."
                        ),
                    }
                )
            elif until <= expiring_cutoff:
                alerts.append(
                    {
                        "code": "OFFLINE_ENVELOPE_EXPIRING_SOON",
                        "severity": "warning",
                        "device_id": device.id,
                        "device_name": device.name,
                        "offline_valid_until": until_raw,
                        "message": (
                            f"Offline authorization for “{device.name}” expires within "
                            f"{EXPIRING_SOON_HOURS}h — renew online soon."
                        ),
                    }
                )

        backlog = push_by_device.get(device.id, {"pending": 0, "failed": 0})
        pending = int(backlog.get("pending", 0))
        failed = int(backlog.get("failed", 0))
        if failed > 0:
            alerts.append(
                {
                    "code": "SYNC_FAILED_OPS",
                    "severity": "critical",
                    "device_id": device.id,
                    "device_name": device.name,
                    "count": failed,
                    "message": (
                        f"{failed} failed sync op(s) for “{device.name}” require administrator review."
                    ),
                }
            )
        if pending >= SYNC_BACKLOG_THRESHOLD:
            alerts.append(
                {
                    "code": "SYNC_BACKLOG_HIGH",
                    "severity": "warning",
                    "device_id": device.id,
                    "device_name": device.name,
                    "count": pending,
                    "message": (
                        f"High sync backlog ({pending} pending) for “{device.name}”. "
                        "Reconnect and flush from POS when online."
                    ),
                }
            )

    if open_conflicts > 0:
        alerts.append(
            {
                "code": "SYNC_CONFLICTS_OPEN",
                "severity": "warning",
                "device_id": None,
                "device_name": None,
                "count": open_conflicts,
                "message": (
                    f"{open_conflicts} open sync conflict(s) need resolution on the Company offline sync page."
                ),
            }
        )

    alerts.sort(key=lambda a: (_severity_rank(str(a.get("severity"))), str(a.get("code"))))

    summary = {
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a.get("severity") == "critical"),
        "warning": sum(1 for a in alerts if a.get("severity") == "warning"),
        "info": sum(1 for a in alerts if a.get("severity") == "info"),
    }
    return {
        "alerts": alerts,
        "summary": summary,
        "generated_at": now.isoformat() + "Z",
        "thresholds": {
            "expiring_soon_hours": EXPIRING_SOON_HOURS,
            "sync_backlog_per_device": SYNC_BACKLOG_THRESHOLD,
        },
    }


async def notify_critical_offline_alerts(
    db: AsyncSession, tenant_id: str
) -> dict[str, Any]:
    """Create security notifications (+ default email) for current critical alerts.

    Push delivery and Offline Complete remain deferred. Uses category=security
    (email default on in notification preferences).
    """
    payload = await collect_offline_alerts(db, tenant_id)
    critical = [a for a in payload["alerts"] if a.get("severity") == "critical"]
    created: list[dict[str, Any]] = []
    for alert in critical:
        note = await create_notification(
            db,
            tenant_id=tenant_id,
            title=f"Offline alert: {alert.get('code')}",
            message=str(alert.get("message") or alert.get("code")),
            category="security",
            entity_type="offline_alert",
            entity_id=alert.get("device_id"),
        )
        if note is not None:
            created.append(
                {
                    "notification_id": note.id,
                    "code": alert.get("code"),
                    "device_id": alert.get("device_id"),
                }
            )
    return {
        "critical_count": len(critical),
        "notifications_created": len(created),
        "notifications": created,
        "alerts": critical,
        "channels": {
            "dashboard": True,
            "email": "security preference (default on)",
            "push": "deferred",
        },
        "message": (
            "Critical offline alerts notified via security channel (dashboard + email when enabled). "
            "Push delivery and Offline Complete remain deferred."
        ),
        "generated_at": payload.get("generated_at"),
    }


async def notify_device_soft_lockdown(
    db: AsyncSession,
    *,
    tenant_id: str,
    device: m.OfflineDevice,
    pending_queue: dict[str, Any] | None = None,
) -> m.Notification | None:
    """Security notify after soft revoke + envelope expiry (not Offline Complete)."""
    pending_total = int((pending_queue or {}).get("pending_total") or 0)
    until = getattr(device, "offline_authorized_until", None)
    until_text = until.isoformat() + "Z" if until else "expired"
    return await create_notification(
        db,
        tenant_id=tenant_id,
        title="Offline device soft-locked",
        message=(
            f"Device “{device.name}” was revoked and its server offline auth envelope was expired "
            f"({until_text}). Sync/rebind blocked; {pending_total} pending queue op(s) retained "
            "(not auto-applied). Remote IndexedDB wipe, push alerts, and Offline Complete remain deferred."
        ),
        category="security",
        entity_type="offline_device",
        entity_id=device.id,
    )
