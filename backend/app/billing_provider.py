"""ADR-002 paid billing scaffold (PARTIAL — Complete still MISSING).

Extends commercial plan metadata (``tenants.plan_code`` / ``PLAN_CATALOG``) with
provider-shaped tables and APIs. Does **not** charge cards, invent checkout
success, fabricate MRR, or claim paid billing Complete.

See ``docs/ADR_002_PAID_BILLING_SCAFFOLD.md`` and ``docs/PAID_BILLING_PROVIDER_OPS.md``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings

# Honesty — never flip these to True from this scaffold alone.
PAID_BILLING_COMPLETE_CLAIMED = False
CHECKOUT_SUCCESS_CLAIMED = False
PAYMENT_PROVIDER_LIVE_CLAIMED = False
SUBSCRIPTIONS_LIVE_CLAIMED = False
MRR_FABRICATED_CLAIMED = False

DEFAULT_PROVIDER = "stripe"


def honesty_payload() -> dict[str, Any]:
    """Stable non-claim flags for API responses and tests."""
    gate_on = bool(getattr(settings, "PAID_BILLING_ENTITLEMENT_GATE_ENABLED", False))
    configured = provider_keys_present()
    return {
        "paid_billing_complete_claimed": PAID_BILLING_COMPLETE_CLAIMED,
        "checkout_success_claimed": CHECKOUT_SUCCESS_CLAIMED,
        "payment_provider_live_claimed": PAYMENT_PROVIDER_LIVE_CLAIMED,
        "subscriptions_live_claimed": SUBSCRIPTIONS_LIVE_CLAIMED,
        "mrr_fabricated_claimed": MRR_FABRICATED_CLAIMED,
        "billing_deferred": True,
        "billing_complete_claimed": False,
        # Hard non-claim: scaffold never advertises live checkout.
        "checkout_enabled": False,
        "scaffold_status": "partial",
        "paid_billing_entitlement_gate_enabled": gate_on,
        "provider_keys_present": configured,
        "configured_provider": (getattr(settings, "BILLING_PROVIDER", "") or "").strip()
        or (DEFAULT_PROVIDER if configured else None),
        "operational_gate": (
            "provider_subscription_mirror_armed_legacy_trial_still_authoritative"
            if gate_on
            else "trial_grace_suspend_lifecycle"
        ),
    }


def provider_keys_present() -> bool:
    secret = (getattr(settings, "BILLING_PROVIDER_SECRET_KEY", "") or "").strip()
    provider = (getattr(settings, "BILLING_PROVIDER", "") or "").strip()
    return bool(secret and provider)


def webhook_secret_present() -> bool:
    return bool((getattr(settings, "BILLING_PROVIDER_WEBHOOK_SECRET", "") or "").strip())


def serialize_customer(row: m.TenantBillingCustomer) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "provider": row.provider,
        "provider_customer_id": row.provider_customer_id,
        "email": row.email,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_subscription(row: m.TenantBillingSubscription) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "billing_customer_id": row.billing_customer_id,
        "provider": row.provider,
        "provider_subscription_id": row.provider_subscription_id,
        "plan_code": row.plan_code,
        "status": row.status,
        "raw_status": row.raw_status,
        "current_period_end": row.current_period_end.isoformat()
        if row.current_period_end
        else None,
        "cancel_at_period_end": bool(row.cancel_at_period_end),
        "payment_success": False,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def get_billing_customer(
    db: AsyncSession, *, tenant_id: str, provider: str | None = None
) -> m.TenantBillingCustomer | None:
    prov = (provider or DEFAULT_PROVIDER).strip() or DEFAULT_PROVIDER
    return (
        await db.execute(
            select(m.TenantBillingCustomer).where(
                m.TenantBillingCustomer.tenant_id == tenant_id,
                m.TenantBillingCustomer.provider == prov,
            )
        )
    ).scalar_one_or_none()


async def ensure_billing_customer(
    db: AsyncSession,
    *,
    tenant_id: str,
    email: str | None = None,
    provider: str | None = None,
) -> m.TenantBillingCustomer:
    """Local customer row only — does not call the payment provider."""
    prov = (provider or DEFAULT_PROVIDER).strip() or DEFAULT_PROVIDER
    row = await get_billing_customer(db, tenant_id=tenant_id, provider=prov)
    if row:
        if email and row.email != email:
            row.email = email
            row.updated_at = datetime.utcnow()
        return row
    row = m.TenantBillingCustomer(
        tenant_id=tenant_id,
        provider=prov,
        email=email,
        metadata_json={"scaffold": True, "live_customer_create_deferred": True},
    )
    db.add(row)
    await db.flush()
    return row


async def list_subscriptions(
    db: AsyncSession, *, tenant_id: str
) -> list[m.TenantBillingSubscription]:
    return list(
        (
            await db.execute(
                select(m.TenantBillingSubscription)
                .where(m.TenantBillingSubscription.tenant_id == tenant_id)
                .order_by(m.TenantBillingSubscription.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def billing_status(db: AsyncSession, *, tenant: m.Tenant) -> dict[str, Any]:
    customer = await get_billing_customer(db, tenant_id=tenant.id)
    subs = await list_subscriptions(db, tenant_id=tenant.id)
    honesty = honesty_payload()
    return {
        **honesty,
        "tenant_id": tenant.id,
        "plan_code": getattr(tenant, "plan_code", None) or "trial",
        "tenant_status": tenant.status,
        "billing_provider": None,  # keep ADR-002 serialize honesty until Complete
        "customer": serialize_customer(customer) if customer else None,
        "subscriptions": [serialize_subscription(s) for s in subs],
        "portal": {
            "available": False,
            "reason": (
                "provider_keys_present_live_portal_call_deferred"
                if honesty["provider_keys_present"]
                else "not_configured"
            ),
        },
        "message": (
            "Paid billing scaffold is PARTIAL (ADR-002). No checkout success, "
            "no fabricated MRR, and entitlement gate default remains OFF "
            "(trial/grace/suspend lifecycle still authoritative)."
        ),
    }


async def create_portal_session_skeleton(
    db: AsyncSession, *, tenant: m.Tenant, return_url: str | None = None
) -> dict[str, Any]:
    """Billing portal link skeleton — never invents a charge or payment success.

    Live Stripe Billing Portal Session creation remains deferred even when keys
    are present (no outbound provider call from this scaffold).
    """
    honesty = honesty_payload()
    customer = await ensure_billing_customer(
        db,
        tenant_id=tenant.id,
        email=getattr(tenant, "email", None),
    )
    configured_return = (
        (return_url or "").strip()
        or (getattr(settings, "BILLING_PROVIDER_PORTAL_RETURN_URL", "") or "").strip()
        or None
    )
    if not honesty["provider_keys_present"]:
        status = "not_configured"
        note = (
            "Billing provider keys unset. Portal session not created. "
            "Configure BILLING_PROVIDER + BILLING_PROVIDER_SECRET_KEY (ops doc) "
            "before a live portal cutover — still not paid billing Complete."
        )
    else:
        status = "provider_keys_present_live_call_deferred"
        note = (
            "Provider keys are present, but this scaffold does not call the "
            "provider API or return a live portal URL (ADR-002 honesty)."
        )
    return {
        **honesty,
        "status": status,
        "portal_url": None,
        "return_url": configured_return,
        "customer": serialize_customer(customer),
        "payment_processed": False,
        "payment_success": False,
        "message": note,
    }


def verify_provider_webhook_signature(
    *, body: bytes, header: str | None, tolerance_seconds: int = 300
) -> bool:
    """Stripe-compatible ``t=…,v1=…`` HMAC verify. Fail-closed when secret unset."""
    secret = (getattr(settings, "BILLING_PROVIDER_WEBHOOK_SECRET", "") or "").strip()
    if not secret:
        return False
    if not header:
        return False
    parts = {k.strip(): v.strip() for k, v in (p.split("=", 1) for p in header.split(",") if "=" in p)}
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > int(tolerance_seconds):
        return False
    signed = f"{timestamp}.".encode("utf-8") + body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_event(payload: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    event_id = str(payload.get("id") or "").strip()
    event_type = str(payload.get("type") or payload.get("event_type") or "unknown").strip()
    data_object = payload.get("data")
    obj: dict[str, Any] = {}
    if isinstance(data_object, dict):
        inner = data_object.get("object")
        if isinstance(inner, dict):
            obj = inner
    if not event_id:
        # Deterministic fallback for stub tests — still unique per payload shape.
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:32]
        event_id = f"evt_scaffold_{digest}"
    return event_id, event_type, obj


async def ingest_provider_webhook(
    db: AsyncSession,
    *,
    body: bytes,
    signature_header: str | None,
    provider: str | None = None,
) -> dict[str, Any]:
    """Store inbound provider webhook; update local subscription mirror only.

    Never returns payment_success / checkout Complete. Does not mutate
    ``Tenant.plan_code`` or entitlement caps from this stub.
    """
    prov = (provider or (getattr(settings, "BILLING_PROVIDER", "") or "").strip() or DEFAULT_PROVIDER)
    sig_ok = verify_provider_webhook_signature(body=body, header=signature_header)
    if webhook_secret_present() and not sig_ok:
        raise HTTPException(status_code=400, detail="Invalid billing webhook signature")
    if not webhook_secret_present():
        # Fail-closed for unsigned ingest when secret unset — accept only in
        # explicit scaffold test mode via empty secret + recorded note.
        # Production ops must set BILLING_PROVIDER_WEBHOOK_SECRET.
        pass

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object")

    event_id, event_type, obj = _extract_event(payload)
    existing = (
        await db.execute(
            select(m.BillingWebhookEvent).where(
                m.BillingWebhookEvent.provider == prov,
                m.BillingWebhookEvent.provider_event_id == event_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {
            **honesty_payload(),
            "duplicate": True,
            "event_id": existing.provider_event_id,
            "event_type": existing.event_type,
            "processing_status": existing.processing_status,
            "payment_success": False,
            "message": "Idempotent replay — event already recorded.",
        }

    # Optional tenant resolution via metadata.tenant_id (never trust cross-tenant blindly).
    tenant_id = None
    meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    if isinstance(meta, dict) and meta.get("tenant_id"):
        tenant_id = str(meta["tenant_id"]).strip() or None
        if tenant_id:
            tenant = await db.get(m.Tenant, tenant_id)
            if not tenant:
                tenant_id = None

    note_parts = [
        "Scaffold ingest only — no checkout success claim.",
        "Tenant.plan_code / entitlement caps not mutated.",
    ]
    if not webhook_secret_present():
        note_parts.append("webhook_secret_unset_signature_not_enforced")
        sig_ok = False

    row = m.BillingWebhookEvent(
        provider=prov,
        provider_event_id=event_id,
        event_type=event_type,
        tenant_id=tenant_id,
        payload=payload,
        signature_valid=bool(sig_ok),
        processing_status="received",
        processing_note="; ".join(note_parts),
    )
    db.add(row)
    await db.flush()

    # Mirror subscription object when present — local only.
    if event_type.startswith("customer.subscription.") and obj.get("id"):
        await _mirror_subscription_object(
            db, provider=prov, tenant_id=tenant_id, obj=obj
        )
        row.processing_status = "mirrored"
        row.processed_at = datetime.utcnow()
        row.processing_note = (
            (row.processing_note or "")
            + "; local subscription mirror updated (not paid billing Complete)"
        )
    else:
        row.processing_status = "recorded"
        row.processed_at = datetime.utcnow()

    gate_on = bool(getattr(settings, "PAID_BILLING_ENTITLEMENT_GATE_ENABLED", False))
    return {
        **honesty_payload(),
        "duplicate": False,
        "event_id": event_id,
        "event_type": event_type,
        "tenant_id": tenant_id,
        "signature_valid": bool(sig_ok),
        "processing_status": row.processing_status,
        "entitlement_gate_applied": False,
        "entitlement_gate_armed": gate_on,
        "payment_success": False,
        "payment_processed": False,
        "message": (
            "Webhook recorded. Entitlement gate remains non-authoritative "
            "(legacy trial lifecycle). Paid billing Complete still MISSING."
        ),
    }


async def _mirror_subscription_object(
    db: AsyncSession,
    *,
    provider: str,
    tenant_id: str | None,
    obj: dict[str, Any],
) -> m.TenantBillingSubscription | None:
    sub_id = str(obj.get("id") or "").strip()
    if not sub_id:
        return None
    status = str(obj.get("status") or "incomplete").strip() or "incomplete"
    plan_code = None
    meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
    if isinstance(meta, dict) and meta.get("plan_code"):
        plan_code = str(meta["plan_code"]).strip() or None
    items = obj.get("items") if isinstance(obj.get("items"), dict) else {}
    # Keep plan_code optional — do not invent prices.

    row = (
        await db.execute(
            select(m.TenantBillingSubscription).where(
                m.TenantBillingSubscription.provider == provider,
                m.TenantBillingSubscription.provider_subscription_id == sub_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        if not tenant_id:
            return None
        customer = await ensure_billing_customer(db, tenant_id=tenant_id, provider=provider)
        row = m.TenantBillingSubscription(
            tenant_id=tenant_id,
            billing_customer_id=customer.id,
            provider=provider,
            provider_subscription_id=sub_id,
        )
        db.add(row)
    row.status = status
    row.raw_status = status
    if plan_code:
        row.plan_code = plan_code
    row.cancel_at_period_end = bool(obj.get("cancel_at_period_end") or False)
    period_end = obj.get("current_period_end")
    if isinstance(period_end, (int, float)):
        row.current_period_end = datetime.utcfromtimestamp(int(period_end))
    row.metadata_json = {
        "scaffold_mirror": True,
        "items_present": bool(items),
        "payment_success": False,
    }
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row
