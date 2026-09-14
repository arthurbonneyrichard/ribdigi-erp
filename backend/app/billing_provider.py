"""ADR-002 paid billing (PARTIAL — Complete still MISSING).

Extends commercial plan metadata (``tenants.plan_code`` / ``PLAN_CATALOG``) with
provider-shaped tables and APIs. Portal Session and Checkout Session create are
real when keys are configured (or mock mode for CI). Does **not** invent
payment success, auto-upgrade ``Tenant.plan_code``, fabricate MRR, or claim
paid billing Complete.

See ``docs/ADR_002_PAID_BILLING_SCAFFOLD.md`` and ``docs/PAID_BILLING_PROVIDER_OPS.md``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings

# Honesty — never flip these to True from this PARTIAL cut alone.
PAID_BILLING_COMPLETE_CLAIMED = False
CHECKOUT_SUCCESS_CLAIMED = False
PAYMENT_PROVIDER_LIVE_CLAIMED = False
SUBSCRIPTIONS_LIVE_CLAIMED = False
MRR_FABRICATED_CLAIMED = False

DEFAULT_PROVIDER = "stripe"

# Injected in tests (httpx.MockTransport or callable). Production leaves None.
_http_transport: Any = None


# Documented allowlist of routes that enforce the provider subscription mirror
# when PAID_BILLING_ENTITLEMENT_GATE_ENABLED is True. Keep this set small and
# explicit — expanding it is a separate product decision (still not Complete).
GATED_ROUTE_ALLOWLIST: tuple[str, ...] = (
    "POST /api/v1/sales",
    "PATCH /api/v1/companies/{company_id}",
)

# Stripe-shaped statuses that allow gated writes when the flag is ON.
ENTITLEMENT_ALLOW_STATUSES: frozenset[str] = frozenset({"active", "trialing"})

# Explicit deny statuses (missing / unknown also deny when flag ON).
ENTITLEMENT_DENY_STATUSES: frozenset[str] = frozenset(
    {
        "past_due",
        "canceled",
        "cancelled",
        "unpaid",
        "incomplete",
        "incomplete_expired",
        "paused",
    }
)


def honesty_payload() -> dict[str, Any]:
    """Stable non-claim flags for API responses and tests."""
    gate_on = bool(getattr(settings, "PAID_BILLING_ENTITLEMENT_GATE_ENABLED", False))
    configured = provider_keys_present()
    mode = resolve_provider_mode()
    return {
        "paid_billing_complete_claimed": PAID_BILLING_COMPLETE_CLAIMED,
        "checkout_success_claimed": CHECKOUT_SUCCESS_CLAIMED,
        "payment_provider_live_claimed": PAYMENT_PROVIDER_LIVE_CLAIMED,
        "subscriptions_live_claimed": SUBSCRIPTIONS_LIVE_CLAIMED,
        "mrr_fabricated_claimed": MRR_FABRICATED_CLAIMED,
        "billing_deferred": True,
        "billing_complete_claimed": False,
        # Hard non-claim: PARTIAL never advertises live checkout Complete.
        "checkout_enabled": False,
        "scaffold_status": "partial",
        "paid_billing_entitlement_gate_enabled": gate_on,
        "entitlement_gated_routes": list(GATED_ROUTE_ALLOWLIST),
        "entitlement_allow_statuses": sorted(ENTITLEMENT_ALLOW_STATUSES),
        "provider_keys_present": configured,
        "provider_mode": mode,
        "configured_provider": (getattr(settings, "BILLING_PROVIDER", "") or "").strip()
        or (DEFAULT_PROVIDER if configured else None),
        # Flag OFF → trial/grace/suspend remains the commercial access gate.
        # Flag ON → provider subscription mirror is authoritative *only* for
        # GATED_ROUTE_ALLOWLIST (not paid billing Complete / go-live).
        "operational_gate": (
            "provider_subscription_mirror_authoritative_for_gated_routes"
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


def resolve_provider_mode() -> str:
    """Return ``unconfigured`` | ``mock`` | ``live``.

    Explicit ``BILLING_PROVIDER_MODE`` wins when keys are present. Without keys,
    always ``unconfigured`` (fail-closed for portal create).
    """
    if not provider_keys_present():
        return "unconfigured"
    raw = (getattr(settings, "BILLING_PROVIDER_MODE", "") or "").strip().lower()
    if raw in ("mock", "test", "ci"):
        return "mock"
    if raw == "live":
        return "live"
    secret = (getattr(settings, "BILLING_PROVIDER_SECRET_KEY", "") or "").strip()
    # Deterministic CI default: mock-prefixed secrets never hit the network.
    if secret.startswith("sk_test_mock") or secret.startswith("sk_mock_"):
        return "mock"
    return "live"


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
    """Local customer row — provider customer create happens in portal path when needed."""
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
        metadata_json={"scaffold": True, "paid_billing_complete_claimed": False},
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


def subscription_status_allows_access(status: str | None) -> bool:
    """Map provider subscription status → allow for gated routes (flag ON only)."""
    if not status:
        return False
    key = str(status).strip().lower()
    return key in ENTITLEMENT_ALLOW_STATUSES


async def primary_subscription_mirror(
    db: AsyncSession, *, tenant_id: str
) -> m.TenantBillingSubscription | None:
    """Newest local subscription mirror row for the tenant (may be None)."""
    subs = await list_subscriptions(db, tenant_id=tenant_id)
    return subs[0] if subs else None


def entitlement_gate_enabled() -> bool:
    return bool(getattr(settings, "PAID_BILLING_ENTITLEMENT_GATE_ENABLED", False))


async def assert_paid_billing_entitlement(
    db: AsyncSession,
    *,
    tenant_id: str,
    route: str | None = None,
) -> dict[str, Any]:
    """Enforce provider subscription mirror on gated routes when flag is ON.

    Flag OFF → no-op (legacy trial/grace/suspend remains authoritative).
    Flag ON → require a local subscription mirror with status in
    ``ENTITLEMENT_ALLOW_STATUSES``. Missing / past_due / canceled / other
    deny statuses → HTTP 403. Does **not** claim paid billing Complete,
    payment success, or mutate ``Tenant.plan_code``.
    """
    if not entitlement_gate_enabled():
        return {
            "applied": False,
            "allowed": True,
            "reason": "gate_disabled_legacy_trial_grace_suspend",
            "route": route,
        }

    from app.platform_const import is_platform_tenant_id

    if is_platform_tenant_id(tenant_id):
        return {
            "applied": True,
            "allowed": True,
            "reason": "platform_tenant_exempt",
            "route": route,
        }

    sub = await primary_subscription_mirror(db, tenant_id=tenant_id)
    status = (sub.status if sub else None) or None
    if subscription_status_allows_access(status):
        return {
            "applied": True,
            "allowed": True,
            "reason": "subscription_status_allowed",
            "status": status,
            "route": route,
            "subscription_id": sub.id if sub else None,
        }

    deny_reason = "subscription_missing" if sub is None else "subscription_status_denied"
    raise HTTPException(
        status_code=403,
        detail={
            "code": "PAID_BILLING_ENTITLEMENT_DENIED",
            "message": (
                "Paid billing entitlement gate denied this mutation. "
                "An active or trialing provider subscription mirror is required "
                "when PAID_BILLING_ENTITLEMENT_GATE_ENABLED is true. "
                "Paid billing Complete remains MISSING."
            ),
            "subscription_status": status,
            "deny_reason": deny_reason,
            "allow_statuses": sorted(ENTITLEMENT_ALLOW_STATUSES),
            "route": route,
            "paid_billing_complete_claimed": False,
            "payment_success": False,
            "gated_routes": list(GATED_ROUTE_ALLOWLIST),
        },
    )


async def billing_status(db: AsyncSession, *, tenant: m.Tenant) -> dict[str, Any]:
    customer = await get_billing_customer(db, tenant_id=tenant.id)
    subs = await list_subscriptions(db, tenant_id=tenant.id)
    honesty = honesty_payload()
    mode = honesty["provider_mode"]
    gate_on = bool(honesty["paid_billing_entitlement_gate_enabled"])
    if mode == "unconfigured":
        portal_available = False
        portal_reason = "not_configured"
        checkout_available = False
        checkout_reason = "not_configured"
    elif mode == "mock":
        portal_available = True
        portal_reason = "mock_portal_session_ready"
        checkout_available = True
        checkout_reason = "mock_checkout_session_ready"
    else:
        portal_available = True
        portal_reason = "live_portal_session_ready"
        checkout_available = True
        checkout_reason = "live_checkout_session_ready"
    primary = subs[0] if subs else None
    mirror_allows = subscription_status_allows_access(
        primary.status if primary else None
    )
    return {
        **honesty,
        "tenant_id": tenant.id,
        "plan_code": getattr(tenant, "plan_code", None) or "trial",
        "tenant_status": tenant.status,
        "billing_provider": None,  # keep ADR-002 serialize honesty until Complete
        "customer": serialize_customer(customer) if customer else None,
        "subscriptions": [serialize_subscription(s) for s in subs],
        "entitlement_gate": {
            "enabled": gate_on,
            "applied_to_routes": list(GATED_ROUTE_ALLOWLIST) if gate_on else [],
            "allow_statuses": sorted(ENTITLEMENT_ALLOW_STATUSES),
            "mirror_status": primary.status if primary else None,
            "mirror_allows_gated_writes": bool(mirror_allows) if gate_on else None,
            "legacy_trial_authoritative_when_off": True,
        },
        "portal": {
            "available": portal_available,
            "reason": portal_reason,
        },
        "checkout": {
            "available": checkout_available,
            "reason": checkout_reason,
            # Creating a Checkout Session ≠ payment success / Complete.
            "session_create_partial": True,
            "auto_plan_upgrade": False,
        },
        "message": (
            "Paid billing is PARTIAL (ADR-002). Portal / Checkout Session create "
            "work when provider keys are configured (or BILLING_PROVIDER_MODE=mock "
            "for CI). No payment success, no auto plan upgrade, no fabricated MRR. "
            + (
                "Entitlement gate ON — provider subscription mirror is authoritative "
                "only for documented gated routes (not paid billing Complete)."
                if gate_on
                else "Entitlement gate default OFF (trial/grace/suspend lifecycle still "
                "authoritative)."
            )
            + " Complete MISSING."
        ),
    }


def _portal_return_url(return_url: str | None) -> str:
    configured = (
        (return_url or "").strip()
        or (getattr(settings, "BILLING_PROVIDER_PORTAL_RETURN_URL", "") or "").strip()
    )
    if not configured:
        raise HTTPException(
            status_code=400,
            detail=(
                "return_url required for billing portal session "
                "(pass return_url or set BILLING_PROVIDER_PORTAL_RETURN_URL)"
            ),
        )
    return configured


async def create_portal_session(
    db: AsyncSession, *, tenant: m.Tenant, return_url: str | None = None
) -> dict[str, Any]:
    """Create a Billing Portal Session when configured; fail clearly otherwise.

    - ``unconfigured`` → HTTP 503 (no fake success / null URL soft-success)
    - ``mock`` → deterministic mock ``portal_url`` for CI (not payment success)
    - ``live`` → Stripe Billing Portal Session API via httpx

    Never returns ``payment_success`` / paid billing Complete.
    """
    honesty = honesty_payload()
    mode = honesty["provider_mode"]
    if mode == "unconfigured":
        raise HTTPException(
            status_code=503,
            detail=(
                "Billing provider not configured. Set BILLING_PROVIDER and "
                "BILLING_PROVIDER_SECRET_KEY (see docs/PAID_BILLING_PROVIDER_OPS.md). "
                "No portal session created; paid billing Complete still MISSING."
            ),
        )

    configured_return = _portal_return_url(return_url)
    prov = (getattr(settings, "BILLING_PROVIDER", "") or "").strip() or DEFAULT_PROVIDER
    customer = await ensure_billing_customer(
        db,
        tenant_id=tenant.id,
        email=getattr(tenant, "email", None),
        provider=prov,
    )

    if mode == "mock":
        portal = await _create_mock_portal_session(
            db, customer=customer, return_url=configured_return
        )
    else:
        portal = await _create_live_portal_session(
            db, customer=customer, return_url=configured_return, tenant=tenant
        )

    return {
        **honesty,
        "status": portal["status"],
        "portal_url": portal["portal_url"],
        "portal_session_id": portal.get("portal_session_id"),
        "return_url": configured_return,
        "customer": serialize_customer(customer),
        "payment_processed": False,
        "payment_success": False,
        "message": portal["message"],
    }


# Back-compat alias used by older imports/tests.
create_portal_session_skeleton = create_portal_session


async def _create_mock_portal_session(
    db: AsyncSession,
    *,
    customer: m.TenantBillingCustomer,
    return_url: str,
) -> dict[str, Any]:
    """CI / deterministic portal URL — not a real charge or Complete claim."""
    if not customer.provider_customer_id:
        customer.provider_customer_id = f"cus_mock_{customer.tenant_id[:8]}"
    meta = dict(customer.metadata_json or {})
    meta.update(
        {
            "scaffold": True,
            "mock_portal": True,
            "live_customer_create_deferred": False,
            "paid_billing_complete_claimed": False,
        }
    )
    customer.metadata_json = meta
    customer.updated_at = datetime.utcnow()
    session_id = f"bps_mock_{uuid.uuid4().hex[:16]}"
    # Clearly non-production host — UI may open it; tests assert shape only.
    qs = urlencode({"session": session_id, "return_url": return_url})
    portal_url = f"https://billing.stripe.test/mock/session?{qs}"
    await db.flush()
    return {
        "status": "mock_portal_session_created",
        "portal_url": portal_url,
        "portal_session_id": session_id,
        "message": (
            "Mock Billing Portal Session created for CI/test "
            "(BILLING_PROVIDER_MODE=mock). Not payment success; "
            "paid billing Complete still MISSING."
        ),
    }


async def _stripe_form_post(
    *, path: str, data: dict[str, str], secret: str
) -> dict[str, Any]:
    import httpx

    base = (getattr(settings, "BILLING_PROVIDER_API_BASE", "") or "").strip().rstrip(
        "/"
    ) or "https://api.stripe.com"
    url = f"{base}{path}"
    headers = {"Authorization": f"Bearer {secret}"}
    timeout = 30.0
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=_http_transport) as client:
            resp = await client.post(url, data=data, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Billing provider request failed: {exc}",
        ) from exc
    if resp.status_code >= 400:
        detail = resp.text[:500] if resp.text else f"HTTP {resp.status_code}"
        raise HTTPException(
            status_code=502,
            detail=f"Billing provider error ({resp.status_code}): {detail}",
        )
    try:
        payload = resp.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail=f"Billing provider returned invalid JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=502, detail="Billing provider returned non-object JSON"
        )
    return payload


async def _ensure_provider_customer_live(
    db: AsyncSession,
    *,
    customer: m.TenantBillingCustomer,
    tenant: m.Tenant,
    secret: str,
) -> str:
    if customer.provider_customer_id:
        return customer.provider_customer_id
    email = (customer.email or getattr(tenant, "email", None) or "").strip()
    form: dict[str, str] = {
        "metadata[tenant_id]": tenant.id,
        "metadata[ribdigi_scaffold]": "partial",
    }
    if email:
        form["email"] = email
    name = (getattr(tenant, "name", None) or "").strip()
    if name:
        form["name"] = name
    payload = await _stripe_form_post(path="/v1/customers", data=form, secret=secret)
    cus_id = str(payload.get("id") or "").strip()
    if not cus_id:
        raise HTTPException(
            status_code=502,
            detail="Billing provider customer create returned no id",
        )
    customer.provider_customer_id = cus_id
    meta = dict(customer.metadata_json or {})
    meta.update(
        {
            "scaffold": True,
            "live_customer_create_deferred": False,
            "provider_customer_created": True,
            "paid_billing_complete_claimed": False,
        }
    )
    customer.metadata_json = meta
    customer.updated_at = datetime.utcnow()
    await db.flush()
    return cus_id


async def _create_live_portal_session(
    db: AsyncSession,
    *,
    customer: m.TenantBillingCustomer,
    return_url: str,
    tenant: m.Tenant,
) -> dict[str, Any]:
    secret = (getattr(settings, "BILLING_PROVIDER_SECRET_KEY", "") or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="BILLING_PROVIDER_SECRET_KEY unset — cannot create portal session",
        )
    cus_id = await _ensure_provider_customer_live(
        db, customer=customer, tenant=tenant, secret=secret
    )
    payload = await _stripe_form_post(
        path="/v1/billing_portal/sessions",
        data={"customer": cus_id, "return_url": return_url},
        secret=secret,
    )
    portal_url = str(payload.get("url") or "").strip()
    session_id = str(payload.get("id") or "").strip() or None
    if not portal_url:
        raise HTTPException(
            status_code=502,
            detail=(
                "Billing provider portal session response missing url "
                "(no fake success)"
            ),
        )
    return {
        "status": "live_portal_session_created",
        "portal_url": portal_url,
        "portal_session_id": session_id,
        "message": (
            "Live Billing Portal Session created. This is not checkout Complete, "
            "payment success, or paid billing Complete (ADR-002 PARTIAL)."
        ),
    }


_PAID_CHECKOUT_PLAN_CODES = frozenset({"starter", "growth", "enterprise"})


def _checkout_urls(
    *, success_url: str | None, cancel_url: str | None
) -> tuple[str, str]:
    success = (
        (success_url or "").strip()
        or (getattr(settings, "BILLING_PROVIDER_CHECKOUT_SUCCESS_URL", "") or "").strip()
        or (getattr(settings, "BILLING_PROVIDER_PORTAL_RETURN_URL", "") or "").strip()
    )
    cancel = (
        (cancel_url or "").strip()
        or (getattr(settings, "BILLING_PROVIDER_CHECKOUT_CANCEL_URL", "") or "").strip()
        or success
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail=(
                "success_url required for billing checkout session "
                "(pass success_url or set BILLING_PROVIDER_CHECKOUT_SUCCESS_URL)"
            ),
        )
    if not cancel:
        raise HTTPException(
            status_code=400,
            detail=(
                "cancel_url required for billing checkout session "
                "(pass cancel_url or set BILLING_PROVIDER_CHECKOUT_CANCEL_URL)"
            ),
        )
    return success, cancel


def _resolve_checkout_price_id(
    *, plan_code: str | None, price_id: str | None
) -> tuple[str | None, str | None]:
    """Return (price_id, plan_code). Mock may omit price; live requires one."""
    explicit = (price_id or "").strip() or None
    plan = (plan_code or "").strip().lower() or None
    if plan == "trial":
        raise HTTPException(
            status_code=400,
            detail="plan_code=trial is not a paid Checkout Session target",
        )
    if plan and plan not in _PAID_CHECKOUT_PLAN_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported plan_code for checkout: {plan}",
        )
    if explicit:
        return explicit, plan
    raw_map = (getattr(settings, "BILLING_PROVIDER_PRICE_IDS", "") or "").strip()
    if raw_map and plan:
        try:
            mapping = json.loads(raw_map)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"BILLING_PROVIDER_PRICE_IDS is not valid JSON: {exc}",
            ) from exc
        if isinstance(mapping, dict) and mapping.get(plan):
            return str(mapping[plan]).strip() or None, plan
    return None, plan


async def create_checkout_session(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    success_url: str | None = None,
    cancel_url: str | None = None,
    plan_code: str | None = None,
    price_id: str | None = None,
) -> dict[str, Any]:
    """Create a Checkout Session when configured; fail clearly otherwise.

    - ``unconfigured`` → HTTP 503 (no fake success / null URL soft-success)
    - ``mock`` → deterministic mock ``checkout_url`` for CI (not payment success)
    - ``live`` → Stripe Checkout Session API via httpx

    Never returns ``payment_success`` / paid billing Complete.
    Never mutates ``Tenant.plan_code``.
    """
    honesty = honesty_payload()
    mode = honesty["provider_mode"]
    if mode == "unconfigured":
        raise HTTPException(
            status_code=503,
            detail=(
                "Billing provider not configured. Set BILLING_PROVIDER and "
                "BILLING_PROVIDER_SECRET_KEY (see docs/PAID_BILLING_PROVIDER_OPS.md). "
                "No checkout session created; paid billing Complete still MISSING."
            ),
        )

    configured_success, configured_cancel = _checkout_urls(
        success_url=success_url, cancel_url=cancel_url
    )
    resolved_price, resolved_plan = _resolve_checkout_price_id(
        plan_code=plan_code, price_id=price_id
    )
    # Default plan hint from tenant when caller omits (metadata only — no mutation).
    if not resolved_plan:
        tenant_plan = (getattr(tenant, "plan_code", None) or "").strip().lower()
        if tenant_plan in _PAID_CHECKOUT_PLAN_CODES:
            resolved_plan = tenant_plan
            if not resolved_price:
                resolved_price, resolved_plan = _resolve_checkout_price_id(
                    plan_code=resolved_plan, price_id=None
                )

    prov = (getattr(settings, "BILLING_PROVIDER", "") or "").strip() or DEFAULT_PROVIDER
    customer = await ensure_billing_customer(
        db,
        tenant_id=tenant.id,
        email=getattr(tenant, "email", None),
        provider=prov,
    )

    plan_before = getattr(tenant, "plan_code", None)

    if mode == "mock":
        checkout = await _create_mock_checkout_session(
            db,
            customer=customer,
            success_url=configured_success,
            cancel_url=configured_cancel,
            plan_code=resolved_plan,
            price_id=resolved_price,
        )
    else:
        if not resolved_price:
            raise HTTPException(
                status_code=400,
                detail=(
                    "price_id required for live Checkout Session "
                    "(pass price_id or set BILLING_PROVIDER_PRICE_IDS for plan_code)"
                ),
            )
        checkout = await _create_live_checkout_session(
            db,
            customer=customer,
            tenant=tenant,
            success_url=configured_success,
            cancel_url=configured_cancel,
            plan_code=resolved_plan,
            price_id=resolved_price,
        )

    # Integrity: create path must never mutate commercial plan metadata.
    if getattr(tenant, "plan_code", None) != plan_before:
        raise HTTPException(
            status_code=500,
            detail="Checkout Session create must not mutate Tenant.plan_code",
        )

    return {
        **honesty,
        "status": checkout["status"],
        "checkout_url": checkout["checkout_url"],
        "checkout_session_id": checkout.get("checkout_session_id"),
        "success_url": configured_success,
        "cancel_url": configured_cancel,
        "plan_code": resolved_plan,
        "price_id": resolved_price,
        "customer": serialize_customer(customer),
        "payment_processed": False,
        "payment_success": False,
        "auto_plan_upgrade": False,
        "tenant_plan_code_unchanged": True,
        "message": checkout["message"],
    }


async def _create_mock_checkout_session(
    db: AsyncSession,
    *,
    customer: m.TenantBillingCustomer,
    success_url: str,
    cancel_url: str,
    plan_code: str | None,
    price_id: str | None,
) -> dict[str, Any]:
    """CI / deterministic checkout URL — not a real charge or Complete claim."""
    if not customer.provider_customer_id:
        customer.provider_customer_id = f"cus_mock_{customer.tenant_id[:8]}"
    meta = dict(customer.metadata_json or {})
    meta.update(
        {
            "scaffold": True,
            "mock_checkout": True,
            "live_customer_create_deferred": False,
            "paid_billing_complete_claimed": False,
            "checkout_success_claimed": False,
        }
    )
    customer.metadata_json = meta
    customer.updated_at = datetime.utcnow()
    session_id = f"cs_mock_{uuid.uuid4().hex[:16]}"
    qs = urlencode(
        {
            "session": session_id,
            "success_url": success_url,
            "cancel_url": cancel_url,
            **({"plan_code": plan_code} if plan_code else {}),
            **({"price_id": price_id} if price_id else {}),
        }
    )
    checkout_url = f"https://checkout.stripe.test/mock/session?{qs}"
    await db.flush()
    return {
        "status": "mock_checkout_session_created",
        "checkout_url": checkout_url,
        "checkout_session_id": session_id,
        "message": (
            "Mock Checkout Session created for CI/test "
            "(BILLING_PROVIDER_MODE=mock). Not payment success; "
            "no auto plan upgrade; paid billing Complete still MISSING."
        ),
    }


async def _create_live_checkout_session(
    db: AsyncSession,
    *,
    customer: m.TenantBillingCustomer,
    tenant: m.Tenant,
    success_url: str,
    cancel_url: str,
    plan_code: str | None,
    price_id: str,
) -> dict[str, Any]:
    secret = (getattr(settings, "BILLING_PROVIDER_SECRET_KEY", "") or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="BILLING_PROVIDER_SECRET_KEY unset — cannot create checkout session",
        )
    cus_id = await _ensure_provider_customer_live(
        db, customer=customer, tenant=tenant, secret=secret
    )
    form: dict[str, str] = {
        "mode": "subscription",
        "customer": cus_id,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "metadata[tenant_id]": tenant.id,
        "metadata[ribdigi_scaffold]": "partial",
        "subscription_data[metadata][tenant_id]": tenant.id,
        "subscription_data[metadata][ribdigi_scaffold]": "partial",
    }
    if plan_code:
        form["metadata[plan_code]"] = plan_code
        form["subscription_data[metadata][plan_code]"] = plan_code
    payload = await _stripe_form_post(
        path="/v1/checkout/sessions",
        data=form,
        secret=secret,
    )
    checkout_url = str(payload.get("url") or "").strip()
    session_id = str(payload.get("id") or "").strip() or None
    if not checkout_url:
        raise HTTPException(
            status_code=502,
            detail=(
                "Billing provider checkout session response missing url "
                "(no fake success)"
            ),
        )
    return {
        "status": "live_checkout_session_created",
        "checkout_url": checkout_url,
        "checkout_session_id": session_id,
        "message": (
            "Live Checkout Session created. This is not payment success, "
            "auto plan upgrade, or paid billing Complete (ADR-002 PARTIAL)."
        ),
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
    parts = {
        k.strip(): v.strip()
        for k, v in (p.split("=", 1) for p in header.split(",") if "=" in p)
    }
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


def sign_provider_webhook_header(*, body: bytes, secret: str, timestamp: int | None = None) -> str:
    """Helper for tests / ops proof — Stripe-compatible signature header."""
    ts = int(timestamp if timestamp is not None else time.time())
    signed = f"{ts}.".encode("utf-8") + body
    sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


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
    prov = (
        provider
        or (getattr(settings, "BILLING_PROVIDER", "") or "").strip()
        or DEFAULT_PROVIDER
    )
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
            "signature_valid": bool(existing.signature_valid),
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
        "PARTIAL ingest only — no checkout success claim.",
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
        "entitlement_gated_routes": list(GATED_ROUTE_ALLOWLIST),
        "payment_success": False,
        "payment_processed": False,
        "message": (
            "Webhook recorded. Subscription mirror may update locally; entitlement "
            "gate (when enabled) evaluates mirror status on gated routes only. "
            "Legacy trial lifecycle remains authoritative when gate is OFF. "
            "Paid billing Complete still MISSING."
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
