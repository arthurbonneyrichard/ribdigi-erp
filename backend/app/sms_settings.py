"""Tenant-editable Twilio SMS settings with env fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app import models as m
from app.config import settings


@dataclass(frozen=True)
class SmsConfig:
    account_sid: str
    auth_token: str | None
    from_number: str
    source: str  # tenant | env | none
    enabled: bool = True

    @property
    def configured(self) -> bool:
        return bool(
            (self.account_sid or "").strip()
            and (self.auth_token or "").strip()
            and (self.from_number or "").strip()
        )


def _raw_settings(tenant: m.Tenant | None) -> dict[str, Any]:
    raw = (getattr(tenant, "sms_settings", None) or {}) if tenant else {}
    return dict(raw) if isinstance(raw, dict) else {}


def _decrypt_token(token: str | None) -> str | None:
    if not token:
        return None
    from app.totp import decrypt_secret

    try:
        return decrypt_secret(token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to decrypt Twilio auth token") from exc


def tenant_sms_configured(raw: dict[str, Any]) -> bool:
    return bool(
        (raw.get("account_sid") or "").strip()
        and (raw.get("from_number") or "").strip()
        and (raw.get("auth_token_enc") or "").strip()
    )


def resolve_sms_config(tenant: m.Tenant | None = None) -> SmsConfig:
    """Prefer tenant overrides when SID+from+token set; else process env; else none."""
    raw = _raw_settings(tenant)
    enabled = bool(settings.SMS_ENABLED)
    if tenant_sms_configured(raw):
        return SmsConfig(
            account_sid=str(raw.get("account_sid") or "").strip(),
            auth_token=_decrypt_token(raw.get("auth_token_enc")),
            from_number=str(raw.get("from_number") or "").strip(),
            source="tenant",
            enabled=enabled,
        )
    sid = (settings.TWILIO_ACCOUNT_SID or "").strip()
    token = (settings.TWILIO_AUTH_TOKEN or "").strip()
    from_no = (settings.TWILIO_FROM_NUMBER or "").strip()
    if sid and token and from_no:
        return SmsConfig(
            account_sid=sid,
            auth_token=token,
            from_number=from_no,
            source="env",
            enabled=enabled,
        )
    return SmsConfig(
        account_sid="",
        auth_token=None,
        from_number=(settings.TWILIO_FROM_NUMBER or "").strip(),
        source="none",
        enabled=enabled,
    )


def sms_status(tenant: m.Tenant | None = None) -> dict[str, Any]:
    raw = _raw_settings(tenant)
    cfg = resolve_sms_config(tenant)
    configured = cfg.source in {"tenant", "env"}
    if not settings.SMS_ENABLED:
        mode = "disabled"
    elif configured:
        mode = "twilio"
    else:
        mode = "console"
    return {
        "enabled": bool(settings.SMS_ENABLED),
        "configured": configured,
        "mode": mode,
        "source": cfg.source,
        "from_number": cfg.from_number or None,
        "account_sid": cfg.account_sid or None,
        "account_sid_set": bool(cfg.account_sid),
        "has_auth_token": bool(cfg.auth_token)
        if cfg.source != "none"
        else bool(raw.get("auth_token_enc")),
        "tenant_override": bool(tenant_sms_configured(raw)),
    }


def apply_sms_settings_update(tenant: m.Tenant, payload: dict[str, Any]) -> dict[str, Any]:
    """Merge PATCH fields into tenant.sms_settings. Auth token encrypted; never returned."""
    current = _raw_settings(tenant)
    if "account_sid" in payload and payload["account_sid"] is not None:
        current["account_sid"] = str(payload["account_sid"]).strip()[:64]
    if "from_number" in payload and payload["from_number"] is not None:
        current["from_number"] = str(payload["from_number"]).strip()[:32]
    if payload.get("clear_auth_token"):
        current.pop("auth_token_enc", None)
    elif payload.get("auth_token") is not None and str(payload.get("auth_token") or "") != "":
        from app.totp import encrypt_secret

        current["auth_token_enc"] = encrypt_secret(str(payload["auth_token"]))
    tenant.sms_settings = current
    return sms_status(tenant)
