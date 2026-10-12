"""Platform-owner subscription gateway setup. Secrets stay encrypted."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.billing_gateway import (
    gateway_for_config,
    is_custom_billing_provider,
    normalize_billing_provider,
    validate_custom_base_url,
    validate_flutterwave_base_url,
    validate_paystack_base_url,
)
from app.billing_secrets import decrypt_billing_secret, encrypt_billing_secret
from app.config import settings

_CARD_RE = re.compile(r"(?:\d[ -]?){13,19}")


def _mask(value: str | None) -> str | None:
    text = (value or "").strip()
    if len(text) < 4:
        return None
    return f"…{text[-4:]}"


def _reject_card_text(value: str, label: str) -> str:
    text = (value or "").strip()
    if _CARD_RE.search(text):
        raise HTTPException(status_code=422, detail=f"{label} must not contain a card number")
    return text

GATEWAY_ID = "default"
_SECRET_RE = re.compile(r"^[A-Za-z0-9_\-]{8,200}$")


def _now() -> datetime:
    return datetime.utcnow()


async def _row(db: AsyncSession) -> m.PlatformBillingGateway | None:
    return await db.get(m.PlatformBillingGateway, GATEWAY_ID)


def _check_secret(value: str, label: str) -> str:
    text = _reject_card_text(value, label)
    if not _SECRET_RE.match(text) or "://" in text or "@" in text or " " in text:
        raise HTTPException(status_code=422, detail=f"{label} is not a valid gateway credential")
    return text


def _check_provider_mode(provider: str, mode: str, secret: str | None) -> None:
    if provider == "mock" and mode == "live":
        raise HTTPException(status_code=422, detail="Mock gateway cannot be used for live capture")
    if settings.APP_ENV.lower() == "production" and provider == "mock":
        raise HTTPException(status_code=422, detail="Mock gateway is disabled in production")
    if provider == "paystack" and secret:
        if mode == "sandbox" and not secret.startswith("sk_test_"):
            raise HTTPException(status_code=422, detail="Paystack sandbox requires a test secret key")
        if mode == "live" and not secret.startswith("sk_live_"):
            raise HTTPException(status_code=422, detail="Paystack live mode requires a live secret key")
    if provider == "flutterwave" and secret:
        if mode == "sandbox" and not secret.startswith("FLWSECK_TEST-"):
            raise HTTPException(status_code=422, detail="Flutterwave sandbox requires a test secret key")
        if mode == "live" and (secret.startswith("FLWSECK_TEST-") or not secret.startswith("FLWSECK-")):
            raise HTTPException(status_code=422, detail="Flutterwave live mode requires a live secret key")


async def _audit(db: AsyncSession, *, actor: dict, action: str, details: dict) -> None:
    tenant_id = actor.get("tenant_id")
    if not tenant_id:
        return
    safe = {key: value for key, value in details.items() if "secret" not in key and "token" not in key}
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=actor.get("sub"),
        module="billing",
        action=action,
        entity="platform_billing_gateway",
        entity_id=GATEWAY_ID,
        details=safe,
    )


def public_view(row: m.PlatformBillingGateway | None, *, webhook_url: str) -> dict:
    if row is None:
        return {
            "provider": (settings.BILLING_PROVIDER or "mock").strip().lower(),
            "mode": "sandbox",
            "api_base_url": {
                "paystack": "https://api.paystack.co",
                "flutterwave": "https://api.flutterwave.com",
            }.get((settings.BILLING_PROVIDER or "mock").strip().lower(), "https://api.paystack.co"),
            "enabled": False,
            "connected": False,
            "secret_configured": False,
            "secret_hint": None,
            "webhook_secret_configured": bool((settings.BILLING_WEBHOOK_SECRET or "").strip()),
            "webhook_url": webhook_url,
            "last_test_ok": False,
            "last_test_at": None,
            "last_test_message": None,
            "last_webhook_at": None,
            "last_webhook_outcome": None,
            "setup_error": "Gateway credentials have not been saved",
        }
    hint = None
    if row.secret_enc:
        try:
            hint = _mask(decrypt_billing_secret(row.secret_enc))
        except HTTPException:
            hint = None
    connected = bool(row.enabled and row.last_test_ok and row.secret_enc)
    return {
        "provider": row.provider,
        "mode": row.mode,
        "api_base_url": row.api_base_url,
        "enabled": bool(row.enabled),
        "connected": connected,
        "secret_configured": bool(row.secret_enc),
        "secret_hint": hint,
        "webhook_secret_configured": bool(row.webhook_secret_enc),
        "webhook_url": webhook_url,
        "last_test_ok": bool(row.last_test_ok),
        "last_test_at": row.last_test_at.isoformat() if row.last_test_at else None,
        "last_test_message": row.last_test_message,
        "last_webhook_at": row.last_webhook_at.isoformat() if row.last_webhook_at else None,
        "last_webhook_outcome": row.last_webhook_outcome,
        "setup_error": None if row.last_test_ok else (row.last_test_message or "Connection test has not succeeded"),
    }


def webhook_url_for(request: Request, provider: str) -> str:
    base = str(request.base_url).rstrip("/")
    try:
        name = normalize_billing_provider(provider or "mock")
    except HTTPException:
        name = "mock"
    return f"{base}/api/v1/billing/webhooks/{name}"


async def save_gateway(db: AsyncSession, payload, *, actor: dict, request: Request) -> dict:
    provider = normalize_billing_provider(payload.provider)
    mode = payload.mode.strip().lower()
    secret = _check_secret(payload.secret, "secret") if payload.secret else None
    hook = _check_secret(payload.webhook_secret, "webhook_secret") if payload.webhook_secret else None
    row = await _row(db)
    existing_secret = None
    if row and row.secret_enc:
        try:
            existing_secret = decrypt_billing_secret(row.secret_enc)
        except HTTPException:
            existing_secret = None
    _check_provider_mode(provider, mode, secret or existing_secret)
    base_url = None
    if provider == "paystack":
        base_url = validate_paystack_base_url(payload.api_base_url or "https://api.paystack.co")
    elif provider == "flutterwave":
        base_url = validate_flutterwave_base_url(payload.api_base_url or "https://api.flutterwave.com")
    elif is_custom_billing_provider(provider):
        if not (secret or existing_secret):
            raise HTTPException(status_code=422, detail="Enter the gateway secret")
        if not (payload.api_base_url or "").strip():
            raise HTTPException(status_code=422, detail="Enter the gateway API address")
        base_url = validate_custom_base_url(payload.api_base_url or "")
    if row is None:
        row = m.PlatformBillingGateway(id=GATEWAY_ID, provider=provider, mode=mode)
        db.add(row)
    row.provider = provider
    row.mode = mode
    row.api_base_url = base_url
    if secret:
        row.secret_enc = encrypt_billing_secret(secret)
    elif provider == "mock" and not row.secret_enc:
        row.secret_enc = encrypt_billing_secret("mock_gateway_sandbox")
    if hook:
        row.webhook_secret_enc = encrypt_billing_secret(hook)
    elif provider == "mock" and not row.webhook_secret_enc:
        env_hook = (settings.BILLING_WEBHOOK_SECRET or "").strip() or "mock_webhook_sandbox"
        row.webhook_secret_enc = encrypt_billing_secret(env_hook)
    row.enabled = False
    row.last_test_ok = False
    row.last_test_message = "saved_untested"
    row.updated_by = actor.get("sub")
    row.updated_at = _now()
    await db.flush()
    await _audit(db, actor=actor, action="billing_gateway_saved", details={"provider": provider, "mode": mode})
    return public_view(row, webhook_url=webhook_url_for(request, provider))


async def test_gateway(db: AsyncSession, *, actor: dict, request: Request) -> dict:
    row = await _row(db)
    if row is None or not row.secret_enc:
        raise HTTPException(status_code=422, detail="Save gateway credentials before testing")
    try:
        secret = decrypt_billing_secret(row.secret_enc)
    except HTTPException as exc:
        row.last_test_ok = False
        row.last_test_at = _now()
        row.last_test_message = "credential_unreadable"
        row.enabled = False
        await _audit(db, actor=actor, action="billing_gateway_tested", details={"ok": False, "message": "credential_unreadable"})
        raise exc
    gateway = gateway_for_config(
        provider=row.provider, mode=row.mode, secret=secret, base_url=row.api_base_url
    )
    probe = getattr(gateway, "test_connection", None)
    ok, message = probe() if callable(probe) else (False, "provider_not_supported")
    row.last_test_ok = bool(ok)
    row.last_test_at = _now()
    row.last_test_message = message[:80]
    if not ok:
        row.enabled = False
    row.updated_by = actor.get("sub")
    row.updated_at = _now()
    await db.flush()
    await _audit(
        db,
        actor=actor,
        action="billing_gateway_tested",
        details={"ok": bool(ok), "message": message, "provider": row.provider},
    )
    return public_view(row, webhook_url=webhook_url_for(request, row.provider))


async def set_enabled(db: AsyncSession, *, enabled: bool, actor: dict, request: Request) -> dict:
    row = await _row(db)
    if row is None:
        raise HTTPException(status_code=422, detail="Save gateway credentials first")
    if enabled and not row.last_test_ok:
        raise HTTPException(status_code=422, detail="Run a successful connection test before enabling")
    if enabled and row.provider not in {"mock", "paystack"} and not row.webhook_secret_enc:
        raise HTTPException(status_code=422, detail="Save a webhook secret before enabling")
    row.enabled = bool(enabled)
    row.updated_by = actor.get("sub")
    row.updated_at = _now()
    await db.flush()
    await _audit(
        db,
        actor=actor,
        action="billing_gateway_enabled" if enabled else "billing_gateway_disabled",
        details={"provider": row.provider},
    )
    return public_view(row, webhook_url=webhook_url_for(request, row.provider))


async def rotate_gateway(db: AsyncSession, payload, *, actor: dict, request: Request) -> dict:
    row = await _row(db)
    if row is None:
        raise HTTPException(status_code=422, detail="Save gateway credentials before rotating")
    secret = _check_secret(payload.secret, "secret")
    _check_provider_mode(row.provider, row.mode, secret)
    row.secret_enc = encrypt_billing_secret(secret)
    if payload.webhook_secret:
        row.webhook_secret_enc = encrypt_billing_secret(_check_secret(payload.webhook_secret, "webhook_secret"))
    row.enabled = False
    row.last_test_ok = False
    row.last_test_message = "rotated_untested"
    row.updated_by = actor.get("sub")
    row.updated_at = _now()
    await db.flush()
    await _audit(db, actor=actor, action="billing_gateway_rotated", details={"provider": row.provider})
    return public_view(row, webhook_url=webhook_url_for(request, row.provider))


async def note_webhook(db: AsyncSession, *, provider: str, outcome: str) -> None:
    row = (
        await db.execute(select(m.PlatformBillingGateway).where(m.PlatformBillingGateway.provider == provider))
    ).scalar_one_or_none()
    if row is None:
        return
    row.last_webhook_at = _now()
    row.last_webhook_outcome = (outcome or "")[:40]
    await db.flush()
