"""Read-only, secret-free platform operations settings for the software owner."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import saas_billing as billing_svc
from app.config import settings


def _bool(value: Any) -> bool:
    return bool(value)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _csv_roles(raw: str) -> list[str]:
    return [part.strip().lower() for part in (raw or "").split(",") if part.strip()]


async def build_platform_settings(db: AsyncSession) -> dict[str, Any]:
    """Environment-driven operational values. Nothing here is persisted or editable.

    Gateway fields come from the same visible-provider helper as the billing
    console (a sandbox or untested gateway is never reported as live). No keys,
    secrets, hints or webhook URLs are returned.
    """
    from app import billing_gateway_setup as gateway_setup
    from app.billing_api import _visible_provider

    provider = await _visible_provider(db)
    row = await gateway_setup._row(db)
    ai_provider = (settings.AI_PROVIDER or "none").strip().lower() or "none"
    return {
        "trial_days": _int(settings.TRIAL_DAYS),
        "grace_days": _int(settings.TRIAL_GRACE_DAYS),
        "billing_grace_days": _int(settings.BILLING_GRACE_DAYS),
        "billing_reminder_days": sorted(billing_svc.reminder_days(), reverse=True),
        "billing_max_attempts": _int(settings.BILLING_MAX_ATTEMPTS),
        "billing": {
            "provider": provider["provider"],
            "configured": _bool(provider["configured"]),
            "live_charges": _bool(provider["live_charges"]),
            "gateway_mode": (row.mode if row is not None else None),
            "gateway_enabled": _bool(row.enabled) if row is not None else False,
            "gateway_tested": _bool(row.last_test_ok) if row is not None else False,
        },
        "live_charges": _bool(provider["live_charges"]),
        "auth": {
            "login_2fa_enabled": _bool(settings.LOGIN_2FA_ENABLED),
            "totp_enforced_roles": _csv_roles(settings.TOTP_ENFORCED_ROLES),
            "webauthn_rp_id": (settings.WEBAUTHN_RP_ID or "").strip() or None,
            "access_ttl_minutes": _int(settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            "refresh_ttl_days": _int(settings.REFRESH_TOKEN_EXPIRE_DAYS),
        },
        "services": {
            "rate_limit_enabled": _bool(settings.RATE_LIMIT_ENABLED),
            "rate_limit_backend": (settings.RATE_LIMIT_BACKEND or "auto").strip().lower(),
            "rate_limit_per_minute": _int(settings.RATE_LIMIT_PER_MINUTE),
            "rate_limit_read_per_minute": _int(settings.RATE_LIMIT_READ_PER_MINUTE),
            "rate_limit_auth_per_minute": _int(settings.RATE_LIMIT_AUTH_PER_MINUTE),
            "metrics_enabled": _bool(settings.METRICS_ENABLED),
            "request_log_enabled": _bool(settings.REQUEST_LOG_ENABLED),
            "celery_enabled": _bool(settings.CELERY_ENABLED),
            "email_enabled": _bool(settings.EMAIL_ENABLED),
            "sms_enabled": _bool(settings.SMS_ENABLED),
            "ai_enabled": _bool(settings.AI_ENABLED),
            "ai_provider": ai_provider,
            "ai_security_monitor_enabled": _bool(settings.AI_SECURITY_MONITOR_ENABLED),
            "bank_feed_sync_enabled": _bool(settings.BANK_FEED_SYNC_ENABLED),
            "storage_backend": (settings.STORAGE_BACKEND or "local").strip().lower(),
        },
        "backup": {
            "retention_count": _int(settings.BACKUP_RETENTION_COUNT),
            "interval_minutes": _int(settings.CELERY_BACKUP_INTERVAL_MINUTES),
            "encryption_configured": bool((settings.BACKUP_ENCRYPTION_KEY or "").strip()),
        },
        "audit": {
            "retention_years": _int(settings.AUDIT_RETENTION_YEARS),
            "cold_archive_after_days": _int(settings.AUDIT_COLD_ARCHIVE_AFTER_DAYS),
            "http_middleware_enabled": _bool(settings.AUDIT_HTTP_MIDDLEWARE_ENABLED),
        },
        "deploy": {
            "app_env": (settings.APP_ENV or "development").strip().lower(),
            "release_channel": (settings.RIBDIGI_RELEASE_CHANNEL or "development").strip().lower(),
            "build_id": (settings.RIBDIGI_BUILD_ID or "dev").strip() or "dev",
            "frontend_url": (settings.FRONTEND_URL or "").strip() or None,
        },
        "editable": False,
        "source": "environment",
    }
