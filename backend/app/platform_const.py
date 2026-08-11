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
