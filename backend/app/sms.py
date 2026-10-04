"""Outbound SMS via Twilio with safe development console fallback."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings
from app.sms_settings import SmsConfig, resolve_sms_config

logger = logging.getLogger(__name__)

_DEV_OUTBOX: list[dict[str, Any]] = []


@dataclass
class SmsResult:
    sent: bool
    mode: str  # twilio | console | disabled
    sid: str | None = None
    error: str | None = None
    recipients: list[str] = field(default_factory=list)


def clear_dev_outbox() -> None:
    _DEV_OUTBOX.clear()


def get_dev_outbox() -> list[dict[str, Any]]:
    return list(_DEV_OUTBOX)


def twilio_configured(tenant: Any | None = None) -> bool:
    return resolve_sms_config(tenant).configured


def _delivery_mode(cfg: SmsConfig | None = None) -> str:
    c = cfg or resolve_sms_config(None)
    if not c.enabled:
        return "disabled"
    if c.configured:
        return "twilio"
    return "console"


def sms_status(tenant: Any | None = None) -> dict:
    from app.sms_settings import sms_status as _sms_status

    return _sms_status(tenant)


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d+]", "", str(raw).strip())
    if not cleaned:
        return None
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    digits = re.sub(r"\D", "", cleaned)
    if cleaned.startswith("+"):
        if len(digits) < 8 or len(digits) > 15:
            return None
        return "+" + digits
    if len(digits) < 8 or len(digits) > 15:
        return None
    # Local numbers without country code are accepted as-is for console; Twilio needs E.164
    return digits


async def send_sms(
    *,
    to: str,
    body: str,
    tenant: Any | None = None,
    cfg: SmsConfig | None = None,
) -> SmsResult:
    phone = normalize_phone(to)
    c = cfg or resolve_sms_config(tenant)
    if not phone:
        return SmsResult(sent=False, mode=_delivery_mode(c), error="Invalid phone number", recipients=[])

    mode = _delivery_mode(c)
    recipients = [phone]
    if mode == "disabled":
        return SmsResult(sent=False, mode="disabled", recipients=recipients)

    text = (body or "").strip()
    if not text:
        return SmsResult(sent=False, mode=mode, error="Empty SMS body", recipients=recipients)
    # Keep under typical SMS segment guidance
    if len(text) > 480:
        text = text[:477] + "..."

    record = {"to": phone, "body": text, "mode": mode}

    if mode == "console":
        _DEV_OUTBOX.append(record)
        logger.info("SMS console to=%s body=%s", phone, text[:80])
        return SmsResult(sent=True, mode="console", recipients=recipients)

    sid = (c.account_sid or "").strip()
    token = (c.auth_token or "").strip()
    from_number = (c.from_number or "").strip()
    if not phone.startswith("+"):
        return SmsResult(
            sent=False,
            mode="twilio",
            error="Phone must be E.164 (include country code, e.g. +233...)",
            recipients=recipients,
        )

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    try:
        async with httpx.AsyncClient(timeout=float(settings.SMS_TIMEOUT_SECONDS)) as client:
            response = await client.post(
                url,
                data={"To": phone, "From": from_number, "Body": text},
                auth=(sid, token),
            )
        if response.status_code >= 400:
            detail = response.text[:500]
            _DEV_OUTBOX.append({**record, "delivered": False, "error": detail})
            return SmsResult(sent=False, mode="twilio", recipients=recipients, error=detail)
        payload = response.json()
        message_sid = payload.get("sid")
        _DEV_OUTBOX.append({**record, "delivered": True, "sid": message_sid})
        return SmsResult(sent=True, mode="twilio", sid=message_sid, recipients=recipients)
    except Exception as exc:
        logger.exception("Twilio SMS send failed")
        _DEV_OUTBOX.append({**record, "delivered": False, "error": str(exc)})
        return SmsResult(sent=False, mode="twilio", recipients=recipients, error=str(exc)[:500])


async def send_notification_sms(
    *, to: str, title: str, message: str, tenant: Any | None = None
) -> SmsResult:
    body = f"RIBDIGI: {title} — {message}"
    return await send_sms(to=to, body=body, tenant=tenant)


async def send_test_sms(*, to: str, tenant: Any | None = None) -> SmsResult:
    c = resolve_sms_config(tenant)
    if not c.enabled:
        raise HTTPException(status_code=400, detail="SMS_ENABLED is false")
    mode = _delivery_mode(c)
    if not c.configured and mode != "console":
        raise HTTPException(status_code=400, detail="Twilio is not configured")
    return await send_sms(to=to, body="RIBDIGI ERP test SMS. Delivery is working.", cfg=c, tenant=tenant)
