"""Production security posture helpers (Stage 5 S1)."""

from __future__ import annotations

from app.config import settings


def is_production() -> bool:
    return settings.APP_ENV.lower() == "production"


def openapi_enabled() -> bool:
    """Interactive OpenAPI surfaces are disabled in production."""
    return not is_production()


def security_posture() -> dict:
    """Non-sensitive runtime flags for health / ops checks."""
    from app.rate_limit import rate_limiter

    return {
        "env": settings.APP_ENV,
        "security": {
            "rate_limit_enabled": bool(settings.RATE_LIMIT_ENABLED),
            "rate_limit_backend": rate_limiter.backend,
            "rate_limit_api_per_minute": int(settings.RATE_LIMIT_PER_MINUTE),
            "rate_limit_auth_per_minute": int(settings.RATE_LIMIT_AUTH_PER_MINUTE),
            "rate_limit_require_redis": bool(settings.RATE_LIMIT_REQUIRE_REDIS),
            "celery_enabled": bool(settings.CELERY_ENABLED),
            "cors_origins_count": len(settings.cors_origins),
            "cors_allows_wildcard": any(o == "*" for o in settings.cors_origins),
            "openapi_enabled": openapi_enabled(),
            "debug": bool(settings.DEBUG),
        },
    }
