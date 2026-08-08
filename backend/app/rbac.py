"""Role and permission catalog for RIBDIGI ERP."""

from __future__ import annotations

ROLE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "super_admin": {"*": ["*"]},
    "company_admin": {"*": ["*"]},
    "store_manager": {
        "dashboard": ["read"],
        "inventory": ["read", "write"],
        "sales": ["read", "write"],
        "pos": ["read", "write"],
        "purchasing": ["read"],
        "expenses": ["read", "write", "approve"],
        "accounting": ["read"],
        "credit": ["read", "write"],
        "tax": ["read"],
        "stores": ["read", "write"],
        "reports": ["read"],
        "notifications": ["read", "write"],
        "users": ["read"],
        "audit": ["read"],
        "ai": ["read", "write"],
    },
    "sales_officer": {
        "dashboard": ["read"],
        "inventory": ["read"],
        "sales": ["read", "write"],
        "pos": ["read", "write"],
        "credit": ["read", "write"],
        "customers": ["read", "write"],
        "reports": ["read"],
        "notifications": ["read", "write"],
        "ai": ["read"],
    },
    "inventory_officer": {
        "dashboard": ["read"],
        "inventory": ["read", "write"],
        "purchasing": ["read", "write"],
        "suppliers": ["read", "write"],
        "reports": ["read"],
        "notifications": ["read", "write"],
        "ai": ["read"],
    },
    "accountant": {
        "dashboard": ["read"],
        "inventory": ["read"],
        "sales": ["read"],
        "purchasing": ["read"],
        "expenses": ["read", "write", "approve"],
        "accounting": ["read", "write"],
        "credit": ["read", "write"],
        "tax": ["read", "write"],
        "reports": ["read"],
        "notifications": ["read", "write"],
        "ai": ["read"],
        "audit": ["read"],
    },
    "cashier": {
        "dashboard": ["read"],
        "inventory": ["read"],
        "pos": ["read", "write"],
        "sales": ["read"],
        "notifications": ["read", "write"],
    },
}

VALID_ROLES = set(ROLE_PERMISSIONS.keys())


def permissions_for_role(role: str) -> dict[str, list[str]]:
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["cashier"]).copy()


def has_permission(
    role: str,
    module: str,
    action: str,
    overrides: dict | None = None,
) -> bool:
    """Check module/action permission. Role catalog is base; user overrides win."""
    perms = permissions_for_role(role)
    if overrides:
        perms = {**perms, **overrides}

    if perms.get("*") == ["*"] or "*" in (perms.get("*") or []):
        return True

    module_perms = perms.get(module) or []
    if "*" in module_perms or action in module_perms:
        return True
    if action == "read" and "write" in module_perms:
        return True
    return False
