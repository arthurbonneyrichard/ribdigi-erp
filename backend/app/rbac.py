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
        "purchasing": ["read", "approve"],
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
# Platform owner (super_admin) UI only surfaces /platform + a small ops set;
# tenant roles use the business modules below (see frontend Shell ROLE_NAV_MODULES).
MENU_MODULE_BY_PATH: dict[str, str] = {
    "/platform": "platform",
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
SYSTEM_ROLES = frozenset(VALID_ROLES)


def is_system_role(role: str | None) -> bool:
    return (role or "") in SYSTEM_ROLES


# Record-level scope (BR-3.3). `department` reserved until org units exist.
RECORD_SCOPES = frozenset({"own", "all"})
RECORD_SCOPE_KEY = "_record_scope"

# Default record visibility by role. Approver/admin roles use `all`.
ROLE_RECORD_SCOPE: dict[str, str] = {
    "super_admin": "all",
    "company_admin": "all",
    "store_manager": "all",
    "accountant": "all",
    "inventory_officer": "all",
    "sales_officer": "own",
    "cashier": "own",
}


def permissions_for_role(role: str) -> dict[str, list[str]]:
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["cashier"]).copy()


def normalize_record_scope(value: str | None, *, default: str = "all") -> str:
    scope = (value or default).strip().lower()
    if scope == "department":
        # Org units not modeled yet; treat as all until department linkage ships.
        return "all"
    if scope not in RECORD_SCOPES:
        raise ValueError(f"record_scope must be one of {sorted(RECORD_SCOPES)}")
    return scope


def record_scope_for_role(role: str) -> str:
    return ROLE_RECORD_SCOPE.get(role, "own")


def record_scope_from_permissions(role: str, permissions: dict | None) -> str:
    """Resolve effective record scope: user override wins, else role default."""
    if isinstance(permissions, dict) and RECORD_SCOPE_KEY in permissions:
        raw = permissions.get(RECORD_SCOPE_KEY)
        if isinstance(raw, list) and raw:
            raw = raw[0]
        try:
            return normalize_record_scope(str(raw) if raw is not None else None)
        except ValueError:
            pass
    return record_scope_for_role(role)


def record_scope_for_claims(claims: dict) -> str:
    role = claims.get("role") or "cashier"
    perms = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    return record_scope_from_permissions(role, perms)


def assert_record_access(claims: dict, created_by: str | None) -> None:
    """Enforce own-scope on a single record. Raises 404 to avoid IDOR enumeration."""
    from fastapi import HTTPException

    if record_scope_for_claims(claims) != "own":
        return
    if created_by and created_by == claims.get("sub"):
        return
    raise HTTPException(status_code=404, detail="Record not found")


def apply_created_by_scope(stmt, model, claims: dict):
    """Restrict a SQLAlchemy select to rows created by the current user when scope=own."""
    if record_scope_for_claims(claims) != "own":
        return stmt
    return stmt.where(model.created_by == claims.get("sub"))


def list_role_catalog() -> list[dict]:
    """System roles with permission maps for admin UI."""
    rows = []
    for role in sorted(ROLE_PERMISSIONS.keys()):
        rows.append(
            {
                "role": role,
                "label": ROLE_LABELS.get(role, role),
                "permissions": permissions_for_role(role),
                "record_scope": record_scope_for_role(role),
                "system": True,
            }
        )
    return rows


def serialize_user(user) -> dict:
    """Safe user payload — never include password hashes or TOTP secrets."""
    perms = user.permissions or permissions_for_role(user.role)
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
        "is_active": bool(user.is_active),
        "email_verified": bool(user.email_verified),
        "permissions": perms,
        "record_scope": record_scope_from_permissions(user.role, perms if isinstance(perms, dict) else None),
        "totp_enabled": bool(getattr(user, "totp_enabled", False)),
        "created_at": user.created_at,
    }


def strip_meta_permissions(permissions: dict | None) -> dict:
    if not isinstance(permissions, dict):
        return {}
    return {k: v for k, v in permissions.items() if k != RECORD_SCOPE_KEY and isinstance(v, list)}


def has_permission(
    role: str,
    module: str,
    action: str,
    overrides: dict | None = None,
) -> bool:
    """Check module/action permission. Role catalog is base; user overrides win.

    Custom (non-system) roles use overrides as the full permission map — never merge
    onto a system default, or denied modules would leak from cashier defaults.
    """
    clean_overrides = strip_meta_permissions(overrides)
    if not is_system_role(role):
        perms = clean_overrides
    else:
        perms = permissions_for_role(role)
        if clean_overrides:
            perms = {**perms, **clean_overrides}

    if perms.get("*") == ["*"] or "*" in (perms.get("*") or []):
        return True

    module_perms = perms.get(module) or []
    if "*" in module_perms or action in module_perms:
        return True
    if action == "read" and "write" in module_perms:
        return True
    return False
