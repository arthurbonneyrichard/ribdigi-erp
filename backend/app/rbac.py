"""Role and permission catalog for RIBDIGI ERP."""

from __future__ import annotations

ROLE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "super_admin": {"*": ["*"]},
    # Software-owner / RIBDIGI platform staff (home tenant = platform workspace)
    "platform_owner": {"*": ["*"]},
    "platform_admin": {
        "platform": ["read", "write"],
        "platform_tenants": ["read", "write"],
        "platform_packages": ["read", "write"],
        "platform_staff": ["read", "write"],
        "platform_reports": ["read"],
        "users": ["read", "write"],
        "notifications": ["read", "write"],
        "audit": ["read"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "platform_support": {
        "platform": ["read"],
        "platform_tenants": ["read", "write"],
        "platform_packages": ["read"],
        "platform_reports": ["read"],
        "users": ["read"],
        "notifications": ["read"],
        "audit": ["read"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "platform_finance": {
        "platform": ["read"],
        "platform_tenants": ["read"],
        "platform_packages": ["read", "write"],
        "platform_reports": ["read"],
        "users": ["read"],
        "notifications": ["read"],
        "audit": ["read"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "company_admin": {"*": ["*"]},
    "store_manager": {
        "dashboard": ["read"],
        "inventory": ["read", "write"],
        "sales": ["read", "write"],
        "pos": ["read", "write", "approve"],
        "purchasing": ["read", "approve"],
        "expenses": ["read", "write", "approve"],
        "accounting": ["read"],
        "credit": ["read", "write", "approve"],
        "tax": ["read"],
        "stores": ["read", "write"],
        "hotel": ["read", "write"],
        "fmcg": ["read", "write"],
        "hospital": ["read", "write"],
        "reports": ["read"],
        "notifications": ["read", "write"],
        "users": ["read"],
        "audit": ["read"],
        "ai": ["read", "write"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
        "printers": ["read", "write"],
    },
    "sales_officer": {
        "dashboard": ["read"],
        "inventory": ["read"],
        "sales": ["read", "write"],
        "pos": ["read", "write"],
        "credit": ["read", "write"],
        "customers": ["read", "write"],
        "hotel": ["read", "write"],
        "fmcg": ["read", "write"],
        "reports": ["read"],
        "notifications": ["read", "write"],
        "ai": ["read"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
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
        "staff_guide": ["read", "download"],
    },
    "accountant": {
        "dashboard": ["read"],
        "inventory": ["read"],
        "sales": ["read"],
        "purchasing": ["read"],
        "expenses": ["read", "write", "approve"],
        "accounting": ["read", "write"],
        "credit": ["read", "write", "approve"],
        "tax": ["read", "write"],
        "reports": ["read"],
        "notifications": ["read", "write"],
        "ai": ["read"],
        "audit": ["read"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "cashier": {
        "dashboard": ["read"],
        "inventory": ["read"],
        "pos": ["read", "write"],
        "sales": ["read"],
        "credit": ["write"],
        "notifications": ["read", "write"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "hotel_manager": {
        "dashboard": ["read"],
        "hotel": ["read", "write"],
        "inventory": ["read", "write"],
        "pos": ["read", "write", "approve"],
        "purchasing": ["read", "write", "approve"],
        "expenses": ["read", "write"],
        "accounting": ["read"],
        "credit": ["read", "write"],
        "reports": ["read"],
        "notifications": ["read", "write"],
        "users": ["read"],
        "audit": ["read"],
        "security": ["read", "write"],
        "company": ["read", "write"],
        "printers": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "hotel_front_desk": {
        "hotel": ["read", "write"],
        "notifications": ["read", "write"],
        "security": ["read", "write"],
        "printers": ["read"],
        "staff_guide": ["read", "download"],
    },
    "hotel_reservations": {
        "hotel": ["read", "write"],
        "notifications": ["read", "write"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "hotel_housekeeping": {
        "hotel": ["read", "write"],
        "inventory": ["read"],
        "notifications": ["read"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "hotel_maintenance": {
        "hotel": ["read", "write"],
        "inventory": ["read"],
        "notifications": ["read"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "hotel_cashier": {
        "hotel": ["read", "write"],
        "pos": ["read", "write"],
        "accounting": ["read"],
        "notifications": ["read", "write"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
    "hotel_auditor": {
        "hotel": ["read"],
        "reports": ["read"],
        "audit": ["read"],
        "accounting": ["read"],
        "notifications": ["read"],
        "security": ["read", "write"],
        "staff_guide": ["read", "download"],
    },
}

ROLE_LABELS: dict[str, str] = {
    "super_admin": "Super Admin",
    "platform_owner": "Platform Owner",
    "platform_admin": "Platform Admin",
    "platform_support": "Platform Support",
    "platform_finance": "Platform Finance",
    "company_admin": "Company Admin",
    "store_manager": "Store Manager",
    "sales_officer": "Sales Officer",
    "inventory_officer": "Inventory Officer",
    "accountant": "Accountant",
    "cashier": "Cashier",
    "hotel_manager": "Hotel Manager",
    "hotel_front_desk": "Front Desk",
    "hotel_reservations": "Reservations",
    "hotel_housekeeping": "Housekeeping",
    "hotel_maintenance": "Maintenance",
    "hotel_cashier": "Hotel Cashier",
    "hotel_auditor": "Hotel Auditor",
}

PLATFORM_ROLES = frozenset(
    {
        "super_admin",
        "platform_owner",
        "platform_admin",
        "platform_support",
        "platform_finance",
    }
)

PLATFORM_OWNER_ROLES = frozenset({"super_admin", "platform_owner"})
# Hard-delete a company: software owner and platform admin. Support, finance,
# and tenant roles are excluded. super_admin stays the legacy owner equivalent.
PLATFORM_TENANT_DELETE_ROLES = frozenset(
    {"super_admin", "platform_owner", "platform_admin"}
)

# Customer system templates. Hotel_* stay hotel-only; store_manager is the
# retail/store counterpart (hotels use hotel_manager). Shared templates
# (cashier, inventory_officer, accountant, sales_officer, company_admin)
# remain valid across customer industries.
HOTEL_ONLY_ROLES = frozenset(
    {
        "hotel_manager",
        "hotel_front_desk",
        "hotel_reservations",
        "hotel_housekeeping",
        "hotel_maintenance",
        "hotel_cashier",
        "hotel_auditor",
    }
)
RETAIL_ONLY_ROLES = frozenset({"store_manager"})

# Frontend nav href → required module (read). Used for menu filtering.
# Platform owner (super_admin) UI only surfaces /platform + a small ops set;
# tenant roles use the business modules below (see frontend Shell ROLE_NAV_MODULES).
MENU_MODULE_BY_PATH: dict[str, str] = {
    "/platform": "platform",
    "/platform/staff": "platform_staff",
    "/platform/reports": "platform_reports",
    "/dashboard": "dashboard",
    "/company": "company",
    "/inventory": "inventory",
    "/prescriptions": "inventory",
    "/sales": "sales",
    "/pos": "pos",
    "/gift-cards": "pos",
    "/purchasing": "purchasing",
    "/expenses": "expenses",
    "/accounting": "accounting",
    "/credit": "credit",
    "/tax": "tax",
    "/stores": "stores",
    "/hotel": "hotel",
    "/hospital": "hospital",
    "/billing": "accounting",
    "/fmcg": "fmcg",
    "/reports": "reports",
    "/notifications": "notifications",
    "/audit": "audit",
    "/backup": "backup",
    "/jobs": "platform",
    "/integrations": "company",
    "/security": "security",
    "/ai": "ai",
    "/users": "users",
    "/departments": "users",
    "/printers": "printers",
}

VALID_ROLES = set(ROLE_PERMISSIONS.keys())
SYSTEM_ROLES = frozenset(VALID_ROLES)

# Modules that may appear on API keys / custom role permission maps.
SYSTEM_MODULES = frozenset(
    {
        "dashboard",
        "inventory",
        "sales",
        "pos",
        "purchasing",
        "expenses",
        "accounting",
        "credit",
        "tax",
        "stores",
        "hotel",
        "fmcg",
        "hospital",
        "reports",
        "notifications",
        "audit",
        "backup",
        "ai",
        "users",
        "staff_guide",
        "security",
        "company",
        "customers",
        "suppliers",
        "platform",
        "platform_tenants",
        "platform_packages",
        "platform_staff",
        "platform_reports",
        "printers",
    }
)
ALLOWED_ACTIONS = frozenset({"read", "write", "create", "download", "approve", "*"})


def is_system_role(role: str | None) -> bool:
    return (role or "") in SYSTEM_ROLES


def is_platform_role(role: str | None) -> bool:
    return (role or "") in PLATFORM_ROLES


def is_platform_owner_role(role: str | None) -> bool:
    return (role or "") in PLATFORM_OWNER_ROLES


def is_platform_tenant_delete_role(role: str | None) -> bool:
    """Software owner, platform admin, or legacy super_admin."""
    return (role or "") in PLATFORM_TENANT_DELETE_ROLES


def is_wildcard_permission_map(perms: dict | None) -> bool:
    if not isinstance(perms, dict):
        return False
    return perms.get("*") == ["*"] or "*" in (perms.get("*") or [])


def system_role_visible_for_industry(role: str, industry: str | None) -> bool:
    """Whether a system role may appear on a tenant catalog / clone-from list."""
    if role not in VALID_ROLES or role in PLATFORM_ROLES:
        return False
    from app.packages import canonicalize_industry

    ind = canonicalize_industry(industry)
    if role in HOTEL_ONLY_ROLES:
        return ind == "hotel"
    if role in RETAIL_ONLY_ROLES:
        return ind != "hotel"
    return True


def list_customer_system_roles_for_industry(industry: str | None) -> list[str]:
    return sorted(
        role for role in VALID_ROLES if system_role_visible_for_industry(role, industry)
    )


def can_assign_platform_role(actor_role: str, target_role: str) -> bool:
    """Only platform owners can mint owners; admins can mint admin/support/finance."""
    if target_role not in PLATFORM_ROLES:
        return False
    if target_role in PLATFORM_OWNER_ROLES:
        return is_platform_owner_role(actor_role)
    if target_role == "platform_admin":
        return is_platform_owner_role(actor_role) or actor_role == "platform_admin"
    return actor_role in {"super_admin", "platform_owner", "platform_admin"}


# Record-level scope (BR-3.3). department/branch use peer users in the same org unit.
RECORD_SCOPES = frozenset({"own", "department", "branch", "all"})
RECORD_SCOPE_KEY = "_record_scope"

# Default record visibility by role. Approver/admin roles use `all`.
ROLE_RECORD_SCOPE: dict[str, str] = {
    "super_admin": "all",
    "platform_owner": "all",
    "platform_admin": "all",
    "platform_support": "all",
    "platform_finance": "all",
    "company_admin": "all",
    "store_manager": "all",
    "accountant": "all",
    "inventory_officer": "all",
    "sales_officer": "own",
    "cashier": "own",
    "hotel_manager": "all",
    "hotel_front_desk": "all",
    "hotel_reservations": "all",
    "hotel_housekeeping": "all",
    "hotel_maintenance": "all",
    "hotel_cashier": "all",
    "hotel_auditor": "all",
}


def permissions_for_role(role: str) -> dict[str, list[str]]:
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["cashier"]).copy()


def normalize_record_scope(value: str | None, *, default: str = "all") -> str:
    """Normalize record scope (BR-3.3).

    Defense in depth: User*/CustomRole* schema Literals already reject blank/unknown
    with 422. Blank used to become silent default ``all`` (most permissive).
    """
    scope = (value or default).strip().lower()
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
    """Enforce record scope on a single record. Raises 404 to avoid IDOR enumeration."""
    from fastapi import HTTPException

    scope_ids = claims.get("scope_user_ids")
    if scope_ids is None and record_scope_for_claims(claims) == "all":
        return
    if scope_ids is None:
        # Backward compatible: treat missing peer list as own-scope.
        if created_by and created_by == claims.get("sub"):
            return
        raise HTTPException(status_code=404, detail="Record not found")
    if created_by and created_by in scope_ids:
        return
    raise HTTPException(status_code=404, detail="Record not found")


def apply_created_by_scope(stmt, model, claims: dict):
    """Restrict a SQLAlchemy select to rows created by users in the claim scope."""
    scope_ids = claims.get("scope_user_ids")
    if scope_ids is None:
        if record_scope_for_claims(claims) == "all":
            return stmt
        return stmt.where(model.created_by == claims.get("sub"))
    return stmt.where(model.created_by.in_(list(scope_ids)))


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
        "branch_id": getattr(user, "branch_id", None),
        "department_id": getattr(user, "department_id", None),
        "store_id": None,
        "store_ids": [],
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
    if action == "read" and ("write" in module_perms or "create" in module_perms):
        # Till BNPL is credit:write only. AR/AP aging and supplier AP stay credit:read.
        if module == "credit":
            return False
        return True
    if action == "download" and (
        "download" in module_perms or "read" in module_perms or "write" in module_perms
    ):
        return True
    # User Management create/edit uses users:write; accept users:create as the same grant.
    if action in {"write", "create"} and (
        "write" in module_perms or "create" in module_perms
    ):
        return True
    return False


def has_explicit_permission(
    role: str,
    module: str,
    action: str,
    overrides: dict | None = None,
) -> bool:
    """Like has_permission, but write/create do not imply read.

    Cashiers get credit:write for POS buy-now-pay-later tender. That must not open
    supplier AP aging, which remains credit:read.
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
    if action == "download" and (
        "download" in module_perms or "read" in module_perms
    ):
        return True
    if action in {"write", "create"} and (
        "write" in module_perms or "create" in module_perms
    ):
        return True
    return False
