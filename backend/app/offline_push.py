"""Offline Web Push delivery for remote wipe (PARTIAL — not Offline Complete).

Registers browser PushManager subscriptions per offline device and attempts
Web Push when a remote wipe is queued. Without VAPID keys or a subscription,
delivery is honestly skipped (``skipped_unconfigured`` / ``skipped_no_subscription``).

Does **not** claim Offline Complete, push-delivery Complete, or 7-day VERIFIED.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import offline_devices as offline_devices_svc
from app.config import settings

logger = logging.getLogger(__name__)

EVENT_REMOTE_WIPE = "remote_wipe"

STATUS_DELIVERED = "delivered"
STATUS_FAILED = "failed"
STATUS_SKIPPED_NO_SUB = "skipped_no_subscription"
STATUS_SKIPPED_UNCONFIGURED = "skipped_unconfigured"
STATUS_DISABLED = "disabled"

# Injectable sender for tests: (subscription_info, data_str, vapid_private_key, vapid_claims) -> None
_PushSender = Callable[[dict[str, Any], str, str, dict[str, str]], None]
_push_sender: _PushSender | None = None


def set_push_sender(fn: _PushSender | None) -> None:
    """Override Web Push transport (tests). Pass None to restore default."""
    global _push_sender
    _push_sender = fn


def push_configured() -> bool:
    """True when VAPID public+private keys are present (ops enablement)."""
    pub = (settings.OFFLINE_PUSH_VAPID_PUBLIC_KEY or "").strip()
    priv = (settings.OFFLINE_PUSH_VAPID_PRIVATE_KEY or "").strip()
    return bool(pub and priv)


def push_enabled() -> bool:
    return bool(settings.OFFLINE_PUSH_ENABLED) and push_configured()


def vapid_public_key_payload() -> dict[str, Any]:
    """Browser applicationServerKey + honesty flags (no secrets)."""
    configured = push_configured()
    enabled = bool(settings.OFFLINE_PUSH_ENABLED) and configured
    return {
        "configured": configured,
        "enabled": enabled,
        "public_key": (settings.OFFLINE_PUSH_VAPID_PUBLIC_KEY or "").strip() or None,
        "subject": (settings.OFFLINE_PUSH_VAPID_SUBJECT or "").strip() or None,
        "push_delivery_partial": True,
        "push_delivery_complete_claimed": False,
        "offline_complete_claimed": False,
        "message": (
            "Web Push VAPID public key for offline wipe delivery (PARTIAL). "
            "Offline Complete / push-delivery Complete remain deferred."
            if enabled
            else (
                "Web Push not fully configured (set OFFLINE_PUSH_VAPID_* and OFFLINE_PUSH_ENABLED). "
                "Wipe still works via online poll; Offline Complete remains deferred."
            )
        ),
    }


def serialize_subscription(row: m.OfflinePushSubscription) -> dict[str, Any]:
    """Public subscription metadata — never returns p256dh/auth keys."""
    return {
        "id": row.id,
        "device_id": row.device_id,
        "endpoint_host": _endpoint_host(row.endpoint),
        "has_keys": bool(row.p256dh and row.auth),
        "user_agent": row.user_agent,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "last_success_at": row.last_success_at,
        "revoked_at": row.revoked_at,
        "status": "revoked" if row.revoked_at else "active",
    }


def serialize_delivery(row: m.OfflinePushDelivery) -> dict[str, Any]:
    return {
        "id": row.id,
        "device_id": row.device_id,
        "subscription_id": row.subscription_id,
        "event_type": row.event_type,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "response_status": row.response_status,
        "error": row.error,
        "created_at": row.created_at,
        "delivered_at": row.delivered_at,
        "push_delivery_complete_claimed": False,
        "offline_complete_claimed": False,
    }


def _endpoint_host(endpoint: str) -> str | None:
    try:
        return urlparse(endpoint).hostname
    except Exception:
        return None


def _validate_endpoint(endpoint: str) -> str:
    cleaned = (endpoint or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="endpoint must be an absolute http(s) URL")
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in {
        "localhost",
        "127.0.0.1",
        "testserver",
        "host.docker.internal",
    }:
        raise HTTPException(
            status_code=400,
            detail="Push endpoint must use HTTPS (http allowed only for localhost)",
        )
    if len(cleaned) > 2000:
        raise HTTPException(status_code=400, detail="endpoint too long")
    return cleaned


async def get_active_subscription(
    db: AsyncSession, tenant_id: str, device_id: str
) -> m.OfflinePushSubscription | None:
    row = (
        await db.execute(
            select(m.OfflinePushSubscription).where(
                m.OfflinePushSubscription.tenant_id == tenant_id,
                m.OfflinePushSubscription.device_id == device_id,
                m.OfflinePushSubscription.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    return row


async def upsert_subscription(
    db: AsyncSession,
    *,
    tenant_id: str,
    device_id: str,
    endpoint: str,
    p256dh: str,
    auth: str,
    user_agent: str | None = None,
) -> m.OfflinePushSubscription:
    """Bind / refresh a Web Push subscription for an offline device."""
    await offline_devices_svc.get_device(db, tenant_id, device_id)
    endpoint_clean = _validate_endpoint(endpoint)
    key = (p256dh or "").strip()
    auth_key = (auth or "").strip()
    if len(key) < 16 or len(auth_key) < 8:
        raise HTTPException(status_code=400, detail="p256dh and auth keys are required")
    if len(key) > 255 or len(auth_key) > 255:
        raise HTTPException(status_code=400, detail="push keys too long")

    now = datetime.utcnow()
    existing = (
        await db.execute(
            select(m.OfflinePushSubscription).where(
                m.OfflinePushSubscription.tenant_id == tenant_id,
                m.OfflinePushSubscription.device_id == device_id,
            )
        )
    ).scalar_one_or_none()
    ua = (user_agent or "").strip() or None
    if ua and len(ua) > 500:
        ua = ua[:500]

    if existing:
        existing.endpoint = endpoint_clean
        existing.p256dh = key
        existing.auth = auth_key
        existing.user_agent = ua
        existing.revoked_at = None
        existing.updated_at = now
        await db.flush()
        return existing

    row = m.OfflinePushSubscription(
        tenant_id=tenant_id,
        device_id=device_id,
        endpoint=endpoint_clean,
        p256dh=key,
        auth=auth_key,
        user_agent=ua,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    return row


async def revoke_subscription(
    db: AsyncSession, tenant_id: str, device_id: str
) -> m.OfflinePushSubscription | None:
    row = (
        await db.execute(
            select(m.OfflinePushSubscription).where(
                m.OfflinePushSubscription.tenant_id == tenant_id,
                m.OfflinePushSubscription.device_id == device_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        return None
    if row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        row.updated_at = row.revoked_at
        await db.flush()
    return row


def _default_webpush_send(
    subscription_info: dict[str, Any],
    data: str,
    vapid_private_key: str,
    vapid_claims: dict[str, str],
) -> None:
    from pywebpush import webpush

    webpush(
        subscription_info=subscription_info,
        data=data,
        vapid_private_key=vapid_private_key,
        vapid_claims=vapid_claims,
    )


def _resolve_sender() -> _PushSender:
    return _push_sender or _default_webpush_send


async def deliver_remote_wipe_push(
    db: AsyncSession,
    *,
    tenant_id: str,
    device: m.OfflineDevice,
) -> dict[str, Any]:
    """Attempt Web Push notifying the device of a pending remote wipe.

    Always records a delivery row. Never claims Completes.
    """
    payload = {
        "type": EVENT_REMOTE_WIPE,
        "action": EVENT_REMOTE_WIPE,
        "device_id": device.id,
        "wipe_pending": True,
        "message": (
            "Remote wipe requested — clear offline IndexedDB and POST wipe/ack. "
            "Offline Complete remains deferred."
        ),
    }
    now = datetime.utcnow()
    delivery = m.OfflinePushDelivery(
        tenant_id=tenant_id,
        device_id=device.id,
        event_type=EVENT_REMOTE_WIPE,
        payload=payload,
        status="pending",
        attempt_count=0,
        created_at=now,
    )
    db.add(delivery)
    await db.flush()

    honesty = {
        "push_delivery_partial": True,
        "push_delivery_complete_claimed": False,
        "offline_complete_claimed": False,
    }

    if not bool(settings.OFFLINE_PUSH_ENABLED):
        delivery.status = STATUS_DISABLED
        delivery.error = "OFFLINE_PUSH_ENABLED is false"
        await db.flush()
        return {
            **serialize_delivery(delivery),
            **honesty,
            "attempted": False,
            "message": "Push delivery disabled by config; wipe still pending via online poll.",
        }

    if not push_configured():
        delivery.status = STATUS_SKIPPED_UNCONFIGURED
        delivery.error = "VAPID keys not configured"
        await db.flush()
        return {
            **serialize_delivery(delivery),
            **honesty,
            "attempted": False,
            "message": (
                "Push skipped — VAPID not configured. Wipe remains pending for online poll. "
                "Not Offline Complete."
            ),
        }

    sub = await get_active_subscription(db, tenant_id, device.id)
    if not sub:
        delivery.status = STATUS_SKIPPED_NO_SUB
        delivery.error = "No active push subscription for device"
        await db.flush()
        return {
            **serialize_delivery(delivery),
            **honesty,
            "attempted": False,
            "message": (
                "Push skipped — device has no Web Push subscription. "
                "Wipe remains pending for online poll. Not Offline Complete."
            ),
        }

    delivery.subscription_id = sub.id
    delivery.attempt_count = 1
    data_str = json.dumps(payload)
    subscription_info = {
        "endpoint": sub.endpoint,
        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
    }
    vapid_claims = {
        "sub": (settings.OFFLINE_PUSH_VAPID_SUBJECT or "mailto:noreply@localhost").strip()
    }
    try:
        _resolve_sender()(
            subscription_info,
            data_str,
            settings.OFFLINE_PUSH_VAPID_PRIVATE_KEY.strip(),
            vapid_claims,
        )
        delivery.status = STATUS_DELIVERED
        delivery.delivered_at = datetime.utcnow()
        delivery.response_status = 201
        sub.last_success_at = delivery.delivered_at
        sub.updated_at = delivery.delivered_at
        await db.flush()
        return {
            **serialize_delivery(delivery),
            **honesty,
            "attempted": True,
            "message": (
                "Web Push delivered for remote wipe (PARTIAL). "
                "Client must clear IndexedDB and ack. Offline Complete still deferred."
            ),
        }
    except Exception as exc:  # noqa: BLE001 — record honest failure; wipe still pending
        logger.warning("offline wipe push failed device=%s: %s", device.id, exc)
        delivery.status = STATUS_FAILED
        delivery.error = str(exc)[:1000]
        await db.flush()
        return {
            **serialize_delivery(delivery),
            **honesty,
            "attempted": True,
            "message": (
                "Web Push attempt failed; wipe remains pending for online poll. "
                "Offline Complete still deferred."
            ),
        }
