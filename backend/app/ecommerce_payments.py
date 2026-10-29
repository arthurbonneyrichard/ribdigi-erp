"""Tenant storefront payment gateways. Separate from Ribdigi subscription billing."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import ecommerce as ecom
from app import models as m
from app.ecommerce_secrets import decrypt_ecommerce_secret, encrypt_ecommerce_secret, secret_hint
from app.honesty import money_json

PROVIDERS = frozenset({"mock", "paystack", "flutterwave"})


def serialize_gateway(row: m.EcommerceGateway | None) -> dict[str, Any]:
    if row is None:
        return {
            "configured": False,
            "provider": None,
            "mode": "test",
            "secret_configured": False,
            "webhook_secret_configured": False,
            "public_key_hint": None,
            "last_test_ok": False,
        }
    return {
        "configured": bool(row.secret_enc),
        "provider": row.provider,
        "mode": row.mode,
        "secret_configured": bool(row.secret_enc),
        "webhook_secret_configured": bool(row.webhook_secret_enc),
        "public_key_hint": row.public_key_hint,
        "last_test_ok": bool(row.last_test_ok),
    }


async def get_gateway(db: AsyncSession, tenant_id: str) -> m.EcommerceGateway | None:
    return (
        await db.execute(select(m.EcommerceGateway).where(m.EcommerceGateway.tenant_id == tenant_id))
    ).scalar_one_or_none()


async def upsert_gateway(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    provider: str,
    mode: str,
    secret: str | None,
    webhook_secret: str | None,
    public_key: str | None,
) -> m.EcommerceGateway:
    ecom.assert_ecommerce_entitled(tenant)
    name = (provider or "mock").strip().lower()
    if name not in PROVIDERS:
        raise HTTPException(status_code=400, detail="Unsupported storefront payment provider")
    live_mode = (mode or "test").strip().lower()
    if live_mode not in {"test", "live"}:
        raise HTTPException(status_code=400, detail="Mode must be test or live")
    row = await get_gateway(db, tenant.id)
    if row is None:
        row = m.EcommerceGateway(tenant_id=tenant.id, provider=name, mode=live_mode)
        db.add(row)
    row.provider = name
    row.mode = live_mode
    if secret is not None and str(secret).strip():
        row.secret_enc = encrypt_ecommerce_secret(str(secret).strip())
    if webhook_secret is not None and str(webhook_secret).strip():
        row.webhook_secret_enc = encrypt_ecommerce_secret(str(webhook_secret).strip())
    if public_key is not None:
        hint = secret_hint(str(public_key).strip())
        row.public_key_hint = hint
    row.last_test_ok = False
    await db.flush()
    return row


async def mark_gateway_tested(db: AsyncSession, tenant_id: str, *, ok: bool) -> m.EcommerceGateway:
    row = await get_gateway(db, tenant_id)
    if row is None:
        raise HTTPException(status_code=400, detail="Save a storefront payment gateway first")
    row.last_test_ok = bool(ok)
    await db.flush()
    return row


def _signing_secret(row: m.EcommerceGateway) -> str:
    token = row.webhook_secret_enc or row.secret_enc
    if not token:
        raise HTTPException(status_code=400, detail="Storefront webhook secret is not configured")
    return decrypt_ecommerce_secret(token)


def verify_webhook_signature(*, secret: str, body: bytes, signature: str | None) -> bool:
    provided = (signature or "").strip()
    if not provided:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha512).hexdigest()
    if hmac.compare_digest(digest, provided):
        return True
    sha256 = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sha256, provided)


def checkout_url(*, frontend_url: str, tracking_token: str, reference: str) -> str:
    base = (frontend_url or "").rstrip("/")
    return f"{base}/storefront/order/{tracking_token}?ref={reference}"


async def initialize_checkout(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    order: m.EcommerceOrder,
    frontend_url: str,
) -> dict[str, Any]:
    row = await get_gateway(db, tenant.id)
    provider = row.provider if row else "mock"
    reference = order.payment_reference or f"ecom_{order.id.replace('-', '')[:20]}"
    order.payment_reference = reference
    order.payment_provider = provider
    await db.flush()
    return {
        "provider": provider,
        "mode": row.mode if row else "test",
        "reference": reference,
        "amount": money_json(order.total_amount),
        "currency": order.currency,
        "checkout_url": checkout_url(frontend_url=frontend_url, tracking_token=order.tracking_token, reference=reference),
        "paid": False,
        "message": "Complete payment at the processor. The return page does not mark the order paid.",
    }


async def apply_signed_webhook(
    db: AsyncSession,
    *,
    provider: str,
    body: bytes,
    signature: str | None,
    hostname: str | None,
    forwarded_host: str | None,
    preview_token: str | None,
    peer_ip: str | None = None,
) -> dict[str, Any]:
    tenant, _storefront, _domain = await ecom.resolve_public_tenant(
        db,
        host=hostname,
        forwarded_host=forwarded_host,
        preview_token=preview_token,
        peer_ip=peer_ip,
    )
    row = await get_gateway(db, tenant.id)
    if row is None or (row.provider or "").lower() != (provider or "").strip().lower():
        raise HTTPException(status_code=404, detail="Storefront gateway not configured")
    secret = _signing_secret(row)
    if not verify_webhook_signature(secret=secret, body=body, signature=signature):
        raise HTTPException(status_code=401, detail="Invalid storefront webhook signature")
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Webhook body must be JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Webhook body must be a JSON object")

    event_id = str(payload.get("event_id") or payload.get("id") or "").strip()
    reference = str(payload.get("reference") or payload.get("tx_ref") or "").strip()
    amount = payload.get("amount")
    currency = str(payload.get("currency") or "").strip().upper()
    if not event_id or not reference or amount is None or not currency:
        raise HTTPException(
            status_code=400,
            detail="Webhook must include event_id, reference, amount, and currency",
        )

    existing = (
        await db.execute(
            select(m.EcommercePaymentEvent).where(
                m.EcommercePaymentEvent.tenant_id == tenant.id,
                m.EcommercePaymentEvent.provider == row.provider,
                m.EcommercePaymentEvent.event_id == event_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        order = await ecom.get_order(db, tenant.id, existing.order_id) if existing.order_id else None
        return {
            "idempotent": True,
            "paid": bool(order and order.status in ecom.PAID_ORDER_STATUSES),
            "order_id": existing.order_id,
        }

    order = (
        await db.execute(
            select(m.EcommerceOrder).where(
                m.EcommerceOrder.tenant_id == tenant.id,
                m.EcommerceOrder.payment_reference == reference,
            )
        )
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Payment reference does not match a storefront order")
    if money_json(amount) + 1e-9 < money_json(order.total_amount):
        raise HTTPException(status_code=400, detail="Webhook amount does not cover the order")
    if currency != (order.currency or "").upper():
        raise HTTPException(status_code=400, detail="Webhook currency does not match the order")

    digest = hashlib.sha256(body).hexdigest()
    db.add(
        m.EcommercePaymentEvent(
            tenant_id=tenant.id,
            provider=row.provider,
            event_id=event_id,
            order_id=order.id,
            payload_digest=digest,
        )
    )
    await db.flush()
    method = "card" if row.provider != "flutterwave" else "mobile_money"
    order = await ecom.post_paid_order(
        db,
        tenant=tenant,
        order=order,
        payment_method=method,
        payment_reference=reference,
    )
    return {"idempotent": False, "paid": True, "order_id": order.id, "order_number": order.order_number}
