"""Reserved Ribdigi House platform tenant and roles (ADR-137)."""

from __future__ import annotations

PLATFORM_TENANT_ID = "ribdigi-platform"
PLATFORM_TENANT_SLUG = "ribdigi-platform"
PLATFORM_COMPANY_NAME = "Ribdigi House"

PLATFORM_SUPER_ADMIN = "platform_super_admin"
PLATFORM_ADMIN = "platform_admin"

PLATFORM_ROLES = frozenset({PLATFORM_SUPER_ADMIN, PLATFORM_ADMIN})

# Modules for platform RBAC (separate from tenant ERP modules).
PLATFORM_MODULES = frozenset(
    {
        "platform_dashboard",
        "platform_tenants",
        "platform_users",
        "platform_plans",
        "platform_billing",
        "platform_audit",
        "platform_health",
        "platform_settings",
    }
)


def is_platform_tenant_id(tenant_id: str | None) -> bool:
    return (tenant_id or "") == PLATFORM_TENANT_ID


def is_platform_role(role: str | None) -> bool:
    return (role or "") in PLATFORM_ROLES


def principal_for(*, tenant_id: str, role: str) -> str:
    """JWT/login principal: platform staff vs tenant ERP user."""
    if is_platform_tenant_id(tenant_id) and is_platform_role(role):
        return "platform"
    return "tenant"


def home_path_for_principal(principal: str | None) -> str:
    return "/platform/dashboard" if principal == "platform" else "/dashboard"


def path_allowed_for_platform_principal(path: str) -> bool:
    """ADR-137 allowlist: platform APIs + auth/profile/security only."""
    p = (path or "").split("?", 1)[0]
    if p.startswith("/api/v1/platform"):
        return True
    allow_exact = {
        "/api/v1/me",
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
        "/api/v1/auth/idle-logout",
        "/api/v1/auth/sessions",
        "/api/v1/auth/change-password",
        "/api/v1/auth/2fa/status",
        "/api/v1/auth/2fa/setup",
        "/api/v1/auth/2fa/confirm",
        "/api/v1/auth/2fa/disable",
        "/api/v1/auth/2fa/backup-codes",
        "/api/v1/auth/webauthn/register/options",
        "/api/v1/auth/webauthn/register/verify",
        "/api/v1/auth/webauthn/credentials",
        "/api/v1/health",
        "/api/v1/health/ready",
    }
    if p in allow_exact:
        return True
    if p.startswith("/api/v1/auth/sessions/"):
        return True
    if p.startswith("/api/v1/auth/webauthn/credentials/"):
        return True
    return False
