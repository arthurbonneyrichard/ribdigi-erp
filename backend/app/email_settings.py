"""Tenant-editable SMTP settings (BR-20.3) with env fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app import models as m
from app.config import settings


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str | None
    password: str | None
    from_email: str
    from_name: str
    use_tls: bool
    use_ssl: bool
    source: str  # tenant | env | none
    enabled: bool = True

    @property
    def configured(self) -> bool:
        return bool((self.host or "").strip() and (self.from_email or "").strip())


def _raw_settings(tenant: m.Tenant | None) -> dict[str, Any]:
    raw = (getattr(tenant, "email_settings", None) or {}) if tenant else {}
    return dict(raw) if isinstance(raw, dict) else {}


def _decrypt_password(token: str | None) -> str | None:
    if not token:
        return None
    from app.totp import decrypt_secret

    try:
        return decrypt_secret(token)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Unable to decrypt SMTP password") from exc


def tenant_smtp_configured(raw: dict[str, Any]) -> bool:
    return bool((raw.get("host") or "").strip() and (raw.get("from_email") or "").strip())


def resolve_smtp_config(tenant: m.Tenant | None = None) -> SmtpConfig:
    """Prefer tenant overrides when host+from_email set; else process env; else none."""
    raw = _raw_settings(tenant)
    enabled = bool(settings.EMAIL_ENABLED)
    if tenant_smtp_configured(raw):
        return SmtpConfig(
            host=str(raw.get("host") or "").strip(),
            port=int(raw.get("port") or 587),
            username=(str(raw.get("username") or "").strip() or None),
            password=_decrypt_password(raw.get("password_enc")),
            from_email=str(raw.get("from_email") or "").strip(),
            from_name=str(raw.get("from_name") or settings.SMTP_FROM_NAME or "RIBDIGI ERP").strip(),
            use_tls=bool(raw.get("use_tls", True)),
            use_ssl=bool(raw.get("use_ssl", False)),
            source="tenant",
            enabled=enabled,
        )
    host = (settings.SMTP_HOST or "").strip()
    from_email = (settings.SMTP_FROM_EMAIL or "").strip()
    if host and from_email:
        return SmtpConfig(
            host=host,
            port=int(settings.SMTP_PORT or 587),
            username=(settings.SMTP_USER or "").strip() or None,
            password=settings.SMTP_PASSWORD or None,
            from_email=from_email,
            from_name=(settings.SMTP_FROM_NAME or "RIBDIGI ERP").strip(),
            use_tls=bool(settings.SMTP_USE_TLS),
            use_ssl=bool(settings.SMTP_USE_SSL),
            source="env",
            enabled=enabled,
        )
    return SmtpConfig(
        host="",
        port=int(settings.SMTP_PORT or 587),
        username=None,
        password=None,
        from_email=(settings.SMTP_FROM_EMAIL or "noreply@localhost").strip(),
        from_name=(settings.SMTP_FROM_NAME or "RIBDIGI ERP").strip(),
        use_tls=bool(settings.SMTP_USE_TLS),
        use_ssl=bool(settings.SMTP_USE_SSL),
        source="none",
        enabled=enabled,
    )


def email_status(tenant: m.Tenant | None = None) -> dict[str, Any]:
    raw = _raw_settings(tenant)
    cfg = resolve_smtp_config(tenant)
    configured = cfg.source in {"tenant", "env"}
    if not settings.EMAIL_ENABLED:
        mode = "disabled"
    elif configured:
        mode = "smtp"
    else:
        mode = "console"
    return {
        "enabled": bool(settings.EMAIL_ENABLED),
        "configured": configured,
        "mode": mode,
        "source": cfg.source,
        "host": cfg.host or None,
        "port": cfg.port,
        "username": cfg.username,
        "from_email": cfg.from_email or None,
        "from_name": cfg.from_name,
        "use_tls": bool(cfg.use_tls),
        "use_ssl": bool(cfg.use_ssl),
        "frontend_url": settings.FRONTEND_URL,
        "has_password": bool(cfg.password) if cfg.source != "none" else bool(raw.get("password_enc")),
        "tenant_override": bool(tenant_smtp_configured(raw)),
    }


def apply_email_settings_update(tenant: m.Tenant, payload: dict[str, Any]) -> dict[str, Any]:
    """Merge PATCH fields into tenant.email_settings. Password encrypted; never returned."""
    current = _raw_settings(tenant)
    if "host" in payload and payload["host"] is not None:
        current["host"] = str(payload["host"]).strip()[:200]
    if "port" in payload and payload["port"] is not None:
        port = int(payload["port"])
        if port < 1 or port > 65535:
            raise HTTPException(status_code=400, detail="port must be 1–65535")
        current["port"] = port
    if "username" in payload and payload["username"] is not None:
        current["username"] = str(payload["username"]).strip()[:200]
    if "from_email" in payload and payload["from_email"] is not None:
        current["from_email"] = str(payload["from_email"]).strip()[:200]
    if "from_name" in payload and payload["from_name"] is not None:
        current["from_name"] = str(payload["from_name"]).strip()[:120]
    if "use_tls" in payload and payload["use_tls"] is not None:
        current["use_tls"] = bool(payload["use_tls"])
    if "use_ssl" in payload and payload["use_ssl"] is not None:
        current["use_ssl"] = bool(payload["use_ssl"])
    if payload.get("clear_password"):
        current.pop("password_enc", None)
    elif payload.get("password") is not None and str(payload.get("password") or "") != "":
        from app.totp import encrypt_secret

        current["password_enc"] = encrypt_secret(str(payload["password"]))
    # Mutual exclusion: SSL and STARTTLS
    if current.get("use_ssl") and current.get("use_tls", True):
        # Prefer explicit SSL when both set on this update
        if payload.get("use_ssl") is True:
            current["use_tls"] = False
        elif payload.get("use_tls") is True:
            current["use_ssl"] = False
    tenant.email_settings = current
    return email_status(tenant)
