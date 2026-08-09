"""Deterministic AI security monitor (Phase 4 / BR-21.10).

Scans tenant audit logs for unusual login patterns and suspicious
transaction bursts. No external ML required.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

SENSITIVE_ACTIONS = frozenset(
    {
        "create",
        "post",
        "approve",
        "payment",
        "restore_apply",
        "delete",
        "cancel",
        "amend",
        "receive",
        "transfer",
    }
)
SENSITIVE_MODULES = frozenset(
    {
        "accounting",
        "purchasing",
        "sales",
        "expenses",
        "backup",
        "credit",
        "inventory",
        "users",
    }
)


def _risk_level(score: float) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


async def scan_security_alerts(
    db: AsyncSession,
    tenant_id: str,
    *,
    lookback_hours: int = 72,
    notify: bool = False,
) -> dict:
    lookback_hours = max(6, min(int(lookback_hours), 168))
    now = datetime.utcnow()
    since = now - timedelta(hours=lookback_hours)
    history_since = now - timedelta(days=30)

    logs = (
        await db.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.created_at >= history_since,
            )
            .order_by(m.AuditLog.created_at.desc())
        )
    ).scalars().all()

    recent = [e for e in logs if e.created_at and e.created_at >= since]
    alerts: list[dict] = []

    # --- Failed login bursts ---
    failed_by_user: dict[str, list] = defaultdict(list)
    failed_by_ip: dict[str, list] = defaultdict(list)
    for e in recent:
        if e.module == "auth" and e.action == "login_failed":
            if e.user_id:
                failed_by_user[e.user_id].append(e)
            if e.ip_address:
                failed_by_ip[e.ip_address].append(e)

    for uid, events in failed_by_user.items():
        if len(events) < 4:
            continue
        # cluster within 30 minutes
        times = sorted(e.created_at for e in events if e.created_at)
        burst = 1
        max_burst = 1
        window_start = times[0]
        for t in times[1:]:
            if (t - window_start) <= timedelta(minutes=30):
                burst += 1
                max_burst = max(max_burst, burst)
            else:
                window_start = t
                burst = 1
        if max_burst >= 4:
            score = min(95, 40 + max_burst * 10)
            alerts.append(
                {
                    "id": f"failed_login_user:{uid}",
                    "kind": "failed_login_burst",
                    "title": "Repeated failed logins for a user",
                    "detail": (
                        f"{max_burst} failed login attempts for user {uid} "
                        f"within 30 minutes (lookback {lookback_hours}h)."
                    ),
                    "severity": _risk_level(score),
                    "score": score,
                    "entity_type": "user",
                    "entity_id": uid,
                    "indicators": {"failed_count": max_burst, "window_minutes": 30},
                    "detected_at": times[-1],
                }
            )

    for ip, events in failed_by_ip.items():
        if len(events) < 6:
            continue
        score = min(95, 45 + len(events) * 5)
        alerts.append(
            {
                "id": f"failed_login_ip:{ip}",
                "kind": "failed_login_ip_burst",
                "title": "Failed logins from a single IP",
                "detail": f"{len(events)} failed logins from IP {ip} in the last {lookback_hours}h.",
                "severity": _risk_level(score),
                "score": score,
                "entity_type": "ip",
                "entity_id": ip,
                "indicators": {"failed_count": len(events), "ip_address": ip},
                "detected_at": max(e.created_at for e in events if e.created_at),
            }
        )

    # --- Successful login after failures (stuffing) ---
    logins_recent = [
        e for e in recent if e.module == "auth" and e.action == "login" and e.user_id
    ]
    for login in logins_recent:
        prior_fails = [
            f
            for f in failed_by_user.get(login.user_id, [])
            if f.created_at
            and login.created_at
            and timedelta(0) <= (login.created_at - f.created_at) <= timedelta(minutes=45)
        ]
        if len(prior_fails) >= 3:
            score = min(98, 55 + len(prior_fails) * 8)
            alerts.append(
                {
                    "id": f"login_after_fails:{login.id}",
                    "kind": "login_after_failures",
                    "title": "Successful login after multiple failures",
                    "detail": (
                        f"User {login.user_id} logged in after {len(prior_fails)} "
                        f"failed attempts (possible credential stuffing)."
                    ),
                    "severity": _risk_level(score),
                    "score": score,
                    "entity_type": "user",
                    "entity_id": login.user_id,
                    "indicators": {
                        "prior_failures": len(prior_fails),
                        "ip_address": login.ip_address,
                    },
                    "detected_at": login.created_at,
                }
            )

    # --- New IP / unusual hour for login ---
    historical_ips: dict[str, set[str]] = defaultdict(set)
    historical_hours: dict[str, Counter] = defaultdict(Counter)
    for e in logs:
        if e.module != "auth" or e.action != "login" or not e.user_id:
            continue
        if e.created_at and e.created_at < since:
            if e.ip_address:
                historical_ips[e.user_id].add(e.ip_address)
            if e.created_at:
                historical_hours[e.user_id][e.created_at.hour] += 1

    for login in logins_recent:
        uid = login.user_id
        known = historical_ips.get(uid) or set()
        if login.ip_address and known and login.ip_address not in known:
            score = 65
            alerts.append(
                {
                    "id": f"new_ip:{login.id}",
                    "kind": "unusual_login_ip",
                    "title": "Login from a new IP address",
                    "detail": (
                        f"User {uid} logged in from new IP {login.ip_address} "
                        f"(not seen in prior 30 days for this user)."
                    ),
                    "severity": _risk_level(score),
                    "score": score,
                    "entity_type": "user",
                    "entity_id": uid,
                    "indicators": {
                        "ip_address": login.ip_address,
                        "user_agent": login.user_agent,
                        "known_ip_count": len(known),
                    },
                    "detected_at": login.created_at,
                }
            )

        hour = login.created_at.hour if login.created_at else None
        hour_hist = historical_hours.get(uid) or Counter()
        total_hist = sum(hour_hist.values())
        if hour is not None and total_hist >= 5 and hour in range(0, 5):
            typical = sum(hour_hist[h] for h in range(7, 20))
            if typical >= total_hist * 0.6 and hour_hist[hour] == 0:
                score = 55
                alerts.append(
                    {
                        "id": f"odd_hour:{login.id}",
                        "kind": "unusual_login_time",
                        "title": "Login at an unusual hour",
                        "detail": (
                            f"User {uid} logged in at {hour:02d}:00; prior activity "
                            f"is mostly daytime."
                        ),
                        "severity": _risk_level(score),
                        "score": score,
                        "entity_type": "user",
                        "entity_id": uid,
                        "indicators": {"hour": hour, "user_agent": login.user_agent},
                        "detected_at": login.created_at,
                    }
                )

        # New / rare user agent
        if login.user_agent:
            prior_ua = {
                e.user_agent
                for e in logs
                if e.user_id == uid
                and e.module == "auth"
                and e.action == "login"
                and e.created_at
                and e.created_at < since
                and e.user_agent
            }
            if prior_ua and login.user_agent not in prior_ua:
                score = 50
                alerts.append(
                    {
                        "id": f"new_device:{login.id}",
                        "kind": "unusual_login_device",
                        "title": "Login from a new device/user-agent",
                        "detail": f"User {uid} used a user-agent not seen in the prior 30 days.",
                        "severity": _risk_level(score),
                        "score": score,
                        "entity_type": "user",
                        "entity_id": uid,
                        "indicators": {
                            "user_agent": (login.user_agent or "")[:180],
                            "ip_address": login.ip_address,
                        },
                        "detected_at": login.created_at,
                    }
                )

    # --- Suspicious transaction bursts ---
    sensitive = [
        e
        for e in recent
        if (e.module in SENSITIVE_MODULES)
        and (
            e.action in SENSITIVE_ACTIONS
            or any(tok in (e.action or "") for tok in ("post", "approve", "payment", "restore"))
        )
    ]
    by_user_actions: dict[str, list] = defaultdict(list)
    for e in sensitive:
        if e.user_id:
            by_user_actions[e.user_id].append(e)

    for uid, events in by_user_actions.items():
        if len(events) < 8:
            continue
        # count in any 15-minute window
        times = sorted(e.created_at for e in events if e.created_at)
        max_burst = 1
        for i, start in enumerate(times):
            burst = 1
            for t in times[i + 1 :]:
                if (t - start) <= timedelta(minutes=15):
                    burst += 1
                else:
                    break
            max_burst = max(max_burst, burst)
        if max_burst >= 8:
            modules = Counter(e.module for e in events)
            score = min(97, 50 + max_burst * 4)
            alerts.append(
                {
                    "id": f"txn_burst:{uid}",
                    "kind": "suspicious_transaction_burst",
                    "title": "Rapid sensitive transaction pattern",
                    "detail": (
                        f"User {uid} performed {max_burst} sensitive actions "
                        f"within 15 minutes (modules: {', '.join(modules)})."
                    ),
                    "severity": _risk_level(score),
                    "score": score,
                    "entity_type": "user",
                    "entity_id": uid,
                    "indicators": {
                        "burst_count": max_burst,
                        "modules": dict(modules),
                        "window_minutes": 15,
                    },
                    "detected_at": times[-1],
                }
            )

    # Dedupe by id, highest score wins
    by_id: dict[str, dict] = {}
    for a in alerts:
        prev = by_id.get(a["id"])
        if not prev or a["score"] > prev["score"]:
            by_id[a["id"]] = a
    alerts = sorted(by_id.values(), key=lambda a: (-a["score"], a["kind"]))

    notifications_created = 0
    if notify:
        from app.notifications import create_notification

        for a in alerts:
            if a["score"] < 60:
                continue
            existing = (
                await db.execute(
                    select(m.Notification).where(
                        m.Notification.tenant_id == tenant_id,
                        m.Notification.category == "security",
                        m.Notification.title == a["title"],
                        m.Notification.entity_id == (a.get("entity_id") or ""),
                        m.Notification.status == "unread",
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue
            await create_notification(
                db,
                tenant_id=tenant_id,
                category="security",
                title=a["title"],
                message=a["detail"],
                entity_type=a.get("entity_type"),
                entity_id=a.get("entity_id"),
            )
            notifications_created += 1
        await db.flush()

    high = sum(1 for a in alerts if a["severity"] in {"high", "critical"})
    return {
        "generated_at": now,
        "lookback_hours": lookback_hours,
        "method": "rules_v1",
        "alert_count": len(alerts),
        "high_or_critical_count": high,
        "alerts": alerts,
        "notifications_created": notifications_created,
        "note": "Behavioral rules over audit_logs; not a substitute for IDS/SIEM.",
    }
