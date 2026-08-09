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
        "security": ["read", "write"],
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
        "security": ["read", "write"],
    },
    "inventory_officer": {
        "dashboard": ["read"],
        "inventory": ["read", "write"],
        "purchasing": ["read", "write"],
        "suppliers": ["read", "write"],
        "reports": ["read"],
        "notifications": ["read", "write"],
        "ai": ["read"],
        "security": ["read", "write"],
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
        "security": ["read", "write"],
    },
    "cashier": {
        "dashboard": ["read"],
        "inventory": ["read"],
        "pos": ["read", "write"],
        "sales": ["read"],
        "notifications": ["read", "write"],
        "security": ["read", "write"],
    },
}

ROLE_LABELS: dict[str, str] = {
    "super_admin": "Super Admin",
    "company_admin": "Company Admin",
    "store_manager": "Store Manager",
    "sales_officer": "Sales Officer",
    "inventory_officer": "Inventory Officer",
    "accountant": "Accountant",
    "cashier": "Cashier",
}

# Frontend nav href → required module (read). Used for menu filtering.
MENU_MODULE_BY_PATH: dict[str, str] = {
    "/dashboard": "dashboard",
    "/company": "company",
    "/inventory": "inventory",
    "/sales": "sales",
    "/pos": "pos",
    "/purchasing": "purchasing",
    "/expenses": "expenses",
    "/accounting": "accounting",
    "/credit": "credit",
    "/tax": "tax",
    "/stores": "stores",
    "/reports": "reports",
    "/notifications": "notifications",
    "/audit": "audit",
    "/backup": "backup",
    "/security": "security",
    "/ai": "ai",
    "/users": "users",
}

VALID_ROLES = set(ROLE_PERMISSIONS.keys())


def permissions_for_role(role: str) -> dict[str, list[str]]:
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["cashier"]).copy()


def list_role_catalog() -> list[dict]:
    """System roles with permission maps for admin UI."""
    rows = []
    for role in sorted(ROLE_PERMISSIONS.keys()):
        rows.append(
            {
                "role": role,
                "label": ROLE_LABELS.get(role, role),
                "permissions": permissions_for_role(role),
                "system": True,
            }
        )
    return rows


def serialize_user(user) -> dict:
    """Safe user payload — never include password hashes or TOTP secrets."""
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
        "is_active": bool(user.is_active),
        "email_verified": bool(user.email_verified),
        "permissions": user.permissions or permissions_for_role(user.role),
        "totp_enabled": bool(getattr(user, "totp_enabled", False)),
        "created_at": user.created_at,
    }


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
