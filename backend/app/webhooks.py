"""Tenant webhooks with HMAC-SHA256 signatures (Stage 6 W1 / Stage 7 W2 retries)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import totp as totp_svc
from app.config import settings

logger = logging.getLogger(__name__)

VALID_EVENTS: frozenset[str] = frozenset(
    {
        "sale.created",
        "sale.paid",
        "stock.low",
        "stock.in",
        "purchase.order.created",
        "purchase.grn.received",
        "customer.created",
        "expense.approved",
        "user.login",
        "tenant.suspended",
        "webhook.test",
    }
)

SIGNATURE_HEADER = "X-Ribdigi-Signature"
MAX_EVENTS_PER_ENDPOINT = 20
STATUS_PENDING = "pending"
STATUS_PENDING_RETRY = "pending_retry"
STATUS_DELIVERED = "delivered"
STATUS_FAILED = "failed"


def max_attempts() -> int:
    return max(1, int(settings.WEBHOOK_MAX_ATTEMPTS or 5))


def retry_delay_seconds(attempt_count: int) -> int:
    """Exponential backoff after attempt N failed: base * 5^(N-1), capped at 1h."""
    base = max(1, int(settings.WEBHOOK_RETRY_BASE_SECONDS or 60))
    n = max(1, int(attempt_count))
    delay = base * (5 ** (n - 1))
    return min(delay, 3600)


def generate_secret() -> str:
    return f"whsec_{secrets.token_urlsafe(24)}"


def encrypt_webhook_secret(secret: str) -> str:
    return totp_svc.encrypt_secret(secret)


def decrypt_webhook_secret(token: str) -> str:
    return totp_svc.decrypt_secret(token)


def validate_url(url: str) -> str:
    cleaned = (url or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="url must be an absolute http(s) URL")
    host = (parsed.hostname or "").lower()
    if parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "testserver", "host.docker.internal"}:
        raise HTTPException(status_code=400, detail="Webhook URL must use HTTPS (http allowed only for localhost)")
    return cleaned


def normalize_events(events: list | None) -> list[str]:
    if not events:
        raise HTTPException(status_code=400, detail="events must be a non-empty list")
    if not isinstance(events, list):
        raise HTTPException(status_code=400, detail="events must be a list")
    out: list[str] = []
    for raw in events:
        ev = str(raw or "").strip()
        if ev not in VALID_EVENTS:
            raise HTTPException(status_code=400, detail=f"Unsupported event: {raw}")
        if ev not in out:
            out.append(ev)
    if len(out) > MAX_EVENTS_PER_ENDPOINT:
        raise HTTPException(status_code=400, detail=f"At most {MAX_EVENTS_PER_ENDPOINT} events per webhook")
    return out


def sign_payload(*, secret: str, body: bytes, timestamp: int | None = None) -> tuple[str, int]:
    ts = int(timestamp if timestamp is not None else datetime.utcnow().timestamp())
    signed = f"{ts}.".encode("utf-8") + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}", ts


def verify_signature(*, secret: str, body: bytes, header: str, tolerance_seconds: int = 300) -> bool:
    """Verify X-Ribdigi-Signature (used by subscribers / tests)."""
    parts = {}
    for chunk in (header or "").split(","):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip()] = v.strip()
    try:
        ts = int(parts.get("t") or "0")
    except ValueError:
        return False
    expected = parts.get("v1") or ""
    if not expected:
        return False
    now = int(datetime.utcnow().timestamp())
    if abs(now - ts) > tolerance_seconds:
        return False
    recomputed, _ = sign_payload(secret=secret, body=body, timestamp=ts)
    got = recomputed.split("v1=", 1)[-1]
    return hmac.compare_digest(got, expected)


def serialize_endpoint(row: m.WebhookEndpoint, *, include_secret: str | None = None) -> dict[str, Any]:
    data = {
        "id": row.id,
        "url": row.url,
        "events": list(row.events or []),
        "is_active": bool(row.is_active),
        "description": row.description,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "last_delivery_at": row.last_delivery_at,
        "last_status_code": row.last_status_code,
        "failure_count": int(row.failure_count or 0),
    }
    if include_secret:
        data["secret"] = include_secret
        data["secret_shown_once"] = True
    return data


def serialize_delivery(row: m.WebhookDelivery) -> dict[str, Any]:
    return {
        "id": row.id,
        "webhook_id": row.webhook_id,
        "event": row.event,
        "status": row.status,
        "attempt_count": row.attempt_count,
        "response_status": row.response_status,
        "error": row.error,
        "next_retry_at": row.next_retry_at,
        "created_at": row.created_at,
        "delivered_at": row.delivered_at,
    }


async def list_deliveries(
    db: AsyncSession,
    tenant_id: str,
    *,
    webhook_id: str | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[m.WebhookDelivery]:
    """Stage 144 W1 — tenant webhook delivery attempt log (payload excluded from serialize)."""
    stmt = (
        select(m.WebhookDelivery)
        .where(m.WebhookDelivery.tenant_id == tenant_id)
        .order_by(m.WebhookDelivery.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    if webhook_id:
        stmt = stmt.where(m.WebhookDelivery.webhook_id == webhook_id.strip())
    if status:
        stmt = stmt.where(m.WebhookDelivery.status == status.strip().lower())
    return list((await db.execute(stmt)).scalars().all())


async def list_endpoints(
    db: AsyncSession,
    tenant_id: str,
    *,
    active_only: bool = False,
    is_active: bool | None = None,
) -> list[m.WebhookEndpoint]:
    """Stage 126 W1 — is_active / active_only for honest paused-only webhook lists."""
    stmt = select(m.WebhookEndpoint).where(m.WebhookEndpoint.tenant_id == tenant_id)
    if is_active is not None:
        stmt = stmt.where(m.WebhookEndpoint.is_active.is_(bool(is_active)))
    elif active_only:
        stmt = stmt.where(m.WebhookEndpoint.is_active.is_(True))
    rows = (
        await db.execute(stmt.order_by(m.WebhookEndpoint.created_at.desc()))
    ).scalars().all()
    return list(rows)


async def get_endpoint(db: AsyncSession, tenant_id: str, webhook_id: str) -> m.WebhookEndpoint:
    row = (
        await db.execute(
            select(m.WebhookEndpoint).where(
                m.WebhookEndpoint.id == webhook_id,
                m.WebhookEndpoint.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return row


async def create_endpoint(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    url: str,
    events: list | None,
    secret: str | None = None,
    description: str | None = None,
    is_active: bool = True,
) -> tuple[m.WebhookEndpoint, str]:
    cleaned_url = validate_url(url)
    event_list = normalize_events(events)
    raw_secret = (secret or "").strip() or generate_secret()
    if not raw_secret.startswith("whsec_"):
        # Allow custom secrets but normalize empty; non-whsec custom still ok if long enough
        if len(raw_secret) < 16:
            raise HTTPException(status_code=400, detail="secret must be at least 16 characters")
    row = m.WebhookEndpoint(
        tenant_id=tenant_id,
        url=cleaned_url,
        events=event_list,
        secret_enc=encrypt_webhook_secret(raw_secret),
        description=(description or "").strip() or None,
        is_active=bool(is_active),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row, raw_secret


async def update_endpoint(
    db: AsyncSession,
    tenant_id: str,
    webhook_id: str,
    *,
    url: str | None = None,
    events: list | None = None,
    description: str | None = None,
    is_active: bool | None = None,
    rotate_secret: bool = False,
) -> tuple[m.WebhookEndpoint, str | None]:
    row = await get_endpoint(db, tenant_id, webhook_id)
    new_secret: str | None = None
    if url is not None:
        row.url = validate_url(url)
    if events is not None:
        row.events = normalize_events(events)
    if description is not None:
        row.description = description.strip() or None
    if is_active is not None:
        row.is_active = bool(is_active)
    if rotate_secret:
        new_secret = generate_secret()
        row.secret_enc = encrypt_webhook_secret(new_secret)
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row, new_secret


async def delete_endpoint(db: AsyncSession, tenant_id: str, webhook_id: str) -> None:
    row = await get_endpoint(db, tenant_id, webhook_id)
    deliveries = (
        await db.execute(
            select(m.WebhookDelivery).where(
                m.WebhookDelivery.tenant_id == tenant_id,
                m.WebhookDelivery.webhook_id == webhook_id,
            )
        )
    ).scalars().all()
    for d in deliveries:
        await db.delete(d)
    await db.delete(row)
    await db.flush()


def build_envelope(*, tenant_id: str, event: str, data: dict) -> dict:
    return {
        "event": event,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tenant_id": tenant_id,
        "data": data or {},
    }


async def _deliver_http(
    *,
    url: str,
    body: bytes,
    signature_header: str,
    timeout: float = 10.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[int | None, str | None]:
    headers = {
        "Content-Type": "application/json",
        SIGNATURE_HEADER: signature_header,
        "User-Agent": "RIBDIGI-Webhooks/1.0",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False) as client:
            resp = await client.post(url, content=body, headers=headers)
        if 200 <= resp.status_code < 300:
            return resp.status_code, None
        return resp.status_code, f"HTTP {resp.status_code}: {(resp.text or '')[:200]}"
    except Exception as exc:
        return None, str(exc)[:300]


def _apply_attempt_outcome(
    *,
    delivery: m.WebhookDelivery,
    endpoint: m.WebhookEndpoint,
    status_code: int | None,
    error: str | None,
) -> None:
    delivery.attempt_count = int(delivery.attempt_count or 0) + 1
    delivery.response_status = status_code
    endpoint.last_delivery_at = datetime.utcnow()
    endpoint.last_status_code = status_code
    endpoint.updated_at = datetime.utcnow()
    if error:
        delivery.error = error
        endpoint.failure_count = int(endpoint.failure_count or 0) + 1
        if delivery.attempt_count < max_attempts():
            delay = retry_delay_seconds(delivery.attempt_count)
            delivery.status = STATUS_PENDING_RETRY
            delivery.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
            delivery.delivered_at = None
        else:
            delivery.status = STATUS_FAILED
            delivery.next_retry_at = None
    else:
        delivery.status = STATUS_DELIVERED
        delivery.delivered_at = datetime.utcnow()
        delivery.error = None
        delivery.next_retry_at = None
        endpoint.failure_count = 0


async def deliver_to_endpoint(
    db: AsyncSession,
    endpoint: m.WebhookEndpoint,
    *,
    event: str,
    data: dict,
    transport: httpx.AsyncBaseTransport | None = None,
) -> m.WebhookDelivery:
    envelope = build_envelope(tenant_id=endpoint.tenant_id, event=event, data=data)
    body = json.dumps(envelope, sort_keys=True, default=str).encode("utf-8")
    secret = decrypt_webhook_secret(endpoint.secret_enc)
    signature, _ = sign_payload(secret=secret, body=body)
    delivery = m.WebhookDelivery(
        tenant_id=endpoint.tenant_id,
        webhook_id=endpoint.id,
        event=event,
        payload=envelope,
        status=STATUS_PENDING,
        attempt_count=0,
    )
    db.add(delivery)
    await db.flush()

    status_code, error = await _deliver_http(
        url=endpoint.url, body=body, signature_header=signature, transport=transport
    )
    _apply_attempt_outcome(
        delivery=delivery, endpoint=endpoint, status_code=status_code, error=error
    )
    await db.flush()
    return delivery


async def retry_delivery(
    db: AsyncSession,
    delivery: m.WebhookDelivery,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> m.WebhookDelivery:
    """Re-attempt a pending_retry delivery with a freshly signed payload."""
    endpoint = await db.get(m.WebhookEndpoint, delivery.webhook_id)
    if not endpoint or endpoint.tenant_id != delivery.tenant_id:
        delivery.status = STATUS_FAILED
        delivery.error = "Webhook endpoint missing"
        delivery.next_retry_at = None
        await db.flush()
        return delivery
    if not endpoint.is_active:
        delivery.status = STATUS_FAILED
        delivery.error = "Webhook endpoint inactive"
        delivery.next_retry_at = None
        await db.flush()
        return delivery

    envelope = delivery.payload if isinstance(delivery.payload, dict) else {}
    body = json.dumps(envelope, sort_keys=True, default=str).encode("utf-8")
    secret = decrypt_webhook_secret(endpoint.secret_enc)
    signature, _ = sign_payload(secret=secret, body=body)
    status_code, error = await _deliver_http(
        url=endpoint.url, body=body, signature_header=signature, transport=transport
    )
    _apply_attempt_outcome(
        delivery=delivery, endpoint=endpoint, status_code=status_code, error=error
    )
    await db.flush()
    return delivery


async def process_due_retries(
    db: AsyncSession,
    *,
    tenant_id: str | None = None,
    limit: int = 100,
    transport: httpx.AsyncBaseTransport | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Pick up pending_retry rows whose next_retry_at is due (Stage 7 W2)."""
    cutoff = now or datetime.utcnow()
    stmt = (
        select(m.WebhookDelivery)
        .where(
            m.WebhookDelivery.status == STATUS_PENDING_RETRY,
            m.WebhookDelivery.next_retry_at.is_not(None),
            m.WebhookDelivery.next_retry_at <= cutoff,
        )
        .order_by(m.WebhookDelivery.next_retry_at.asc())
        .limit(max(1, int(limit)))
    )
    if tenant_id:
        stmt = stmt.where(m.WebhookDelivery.tenant_id == tenant_id)
    rows = (await db.execute(stmt)).scalars().all()
    retried = 0
    delivered = 0
    failed = 0
    still_pending = 0
    for row in rows:
        updated = await retry_delivery(db, row, transport=transport)
        retried += 1
        if updated.status == STATUS_DELIVERED:
            delivered += 1
        elif updated.status == STATUS_FAILED:
            failed += 1
        elif updated.status == STATUS_PENDING_RETRY:
            still_pending += 1
    return {
        "due": len(rows),
        "retried": retried,
        "delivered": delivered,
        "failed": failed,
        "pending_retry": still_pending,
    }


async def emit_event(
    db: AsyncSession,
    *,
    tenant_id: str,
    event: str,
    data: dict | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list[m.WebhookDelivery]:
    """Fan-out event to active matching webhook endpoints."""
    if event not in VALID_EVENTS:
        return []
    rows = (
        await db.execute(
            select(m.WebhookEndpoint).where(
                m.WebhookEndpoint.tenant_id == tenant_id,
                m.WebhookEndpoint.is_active == True,  # noqa: E712
            )
        )
    ).scalars().all()
    deliveries: list[m.WebhookDelivery] = []
    for ep in rows:
        events = list(ep.events or [])
        if event not in events and "*" not in events:
            continue
        deliveries.append(
            await deliver_to_endpoint(
                db, ep, event=event, data=data or {}, transport=transport
            )
        )
    return deliveries
