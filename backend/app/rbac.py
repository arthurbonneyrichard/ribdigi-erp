"""Role and permission catalog for RIBDIGI ERP."""

from __future__ import annotations

import re
from copy import deepcopy

ROLE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "super_admin": {"*": ["*"]},
    "company_admin": {"*": ["*"]},
    # ADR-137 — Ribdigi House platform staff (platform tenant only)
    "platform_super_admin": {
        "platform_dashboard": ["*"],
        "platform_tenants": ["*"],
        "platform_users": ["*"],
        "platform_plans": ["*"],
        "platform_billing": ["read"],
        "platform_audit": ["*"],
        "platform_health": ["*"],
        "platform_settings": ["*"],
        "security": ["read", "write"],
    },
    "platform_admin": {
        "platform_dashboard": ["read"],
        "platform_tenants": ["read", "write"],
        "platform_users": ["read"],
        "platform_plans": ["read", "write"],
        "platform_billing": ["read"],
        "platform_audit": ["read"],
        "platform_health": ["read"],
        "platform_settings": ["read"],
        "security": ["read", "write"],
    },
    "store_manager": {
        "dashboard": ["read"],
        "inventory": ["read", "write"],
        "sales": ["read", "write"],
        "pos": ["read", "write"],
        "purchasing": ["read", "write", "approve"],
        "expenses": ["read", "write", "approve"],
        "accounting": ["read"],
        "credit": ["read", "write", "approve"],
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
        "credit": ["read", "write", "approve"],
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
    "company_admin": "Tenant Admin",
    "platform_super_admin": "Platform Super Admin",
    "platform_admin": "Platform Admin",
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
    "/activity": "audit",
    "/backup": "backup",
    "/security": "security",
    "/ai": "ai",
    "/users": "users",
    "/admin/roles": "users",
    "/admin/permissions": "users",
}

VALID_ROLES = set(ROLE_PERMISSIONS.keys())
SYSTEM_ROLES = frozenset(VALID_ROLES)

# Modules that custom roles may grant (no tenant/backup/users wildcards by default list).
SYSTEM_MODULES = frozenset(
    {
        "dashboard",
        "company",
        "inventory",
        "sales",
        "pos",
        "purchasing",
        "expenses",
        "accounting",
        "credit",
        "tax",
        "stores",
        "reports",
        "notifications",
        "audit",
        "backup",
        "ai",
        "security",
        "users",
        "customers",
        "suppliers",
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
ALLOWED_ACTIONS = frozenset({"read", "write", "approve", "*"})
_MODULE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
# Stage 84 A1 — common dotted/colon aliases → canonical actions
_ACTION_ALIASES = {
    "view": "read",
    "edit": "write",
    "update": "write",
    "create": "write",
    "delete": "write",
}


def canonicalize_action(action: str) -> str:
    """Map aliased actions (e.g. view→read) to ALLOWED_ACTIONS names."""
    a = str(action or "").strip().lower()
    return _ACTION_ALIASES.get(a, a)


def _split_permission_key(key: str) -> tuple[str, list[str] | None]:
    """Parse module-only or dotted/colon keys.

    Returns ``(module, None)`` for plain modules, or
    ``(module, [action])`` for ``inventory.view`` / ``inventory:read``.
    """
    key = str(key or "").strip().lower()
    if not key:
        return "", None
    if ":" in key:
        module, _, action = key.partition(":")
        module, action = module.strip(), action.strip()
        if module and action and "." not in module:
            return module, [canonicalize_action(action)]
    if "." in key:
        module, _, action = key.partition(".")
        module, action = module.strip(), action.strip()
        # Only treat as module.action when the right side looks like an action alias
        if module and action and (
            action in ALLOWED_ACTIONS or action in _ACTION_ALIASES
        ):
            return module, [canonicalize_action(action)]
    return key, None


def expand_permission_aliases(raw: dict | None) -> dict[str, list[str]]:
    """Best-effort expand dotted/colon keys and action aliases for runtime checks.

    Never raises — invalid entries are skipped.
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}

    def _add(module: str, actions: list[str]) -> None:
        if not module:
            return
        bucket = out.setdefault(module, [])
        for act in actions:
            if act and act not in bucket:
                bucket.append(act)

    for key, actions in raw.items():
        module, dotted = _split_permission_key(str(key or ""))
        if not module or module == RECORD_SCOPE_KEY:
            continue
        if dotted is not None:
            _add(module, dotted)
        if isinstance(actions, str):
            action_list = [canonicalize_action(actions)]
        elif isinstance(actions, list):
            action_list = [canonicalize_action(a) for a in actions if str(a).strip()]
        elif actions in (True, 1, "1"):
            action_list = ["read"] if dotted is None else []
        else:
            action_list = []
        if action_list:
            _add(module, action_list)
    return out


# Record-level scope (BR-3.3). department/branch use peer users in the same org unit.
RECORD_SCOPES = frozenset({"own", "department", "branch", "all"})
RECORD_SCOPE_KEY = "_record_scope"

# Default record visibility by role. Approver/admin roles use `all`.
ROLE_RECORD_SCOPE: dict[str, str] = {
    "super_admin": "all",
    "company_admin": "all",
    "platform_super_admin": "all",
    "platform_admin": "all",
    "store_manager": "all",
    "accountant": "all",
    "inventory_officer": "all",
    "sales_officer": "own",
    "cashier": "own",
}


def permissions_for_role(role: str) -> dict[str, list[str]]:
    """System role permission map. Unknown roles return empty (not cashier) to avoid leaks."""
    if role in ROLE_PERMISSIONS:
        return deepcopy(ROLE_PERMISSIONS[role])
    return {}


def normalize_permissions_map(
    raw: dict | None,
    *,
    allow_wildcard: bool = True,
    allow_platform_modules: bool = False,
) -> dict[str, list[str]]:
    """Validate and normalize a module→actions permission map."""
    from app.platform_const import PLATFORM_MODULES

    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("permissions must be an object")
    out: dict[str, list[str]] = {}

    def _merge(module: str, action_list: list[str]) -> None:
        if module not in out:
            out[module] = []
        for action in action_list:
            if action not in out[module]:
                out[module].append(action)

    for key, actions in raw.items():
        raw_key = str(key or "").strip().lower()
        if not raw_key or raw_key == RECORD_SCOPE_KEY:
            continue
        module, dotted_actions = _split_permission_key(raw_key)
        if module == "*":
            if not allow_wildcard:
                raise ValueError("Custom roles cannot use wildcard '*' module permissions")
            if actions == ["*"] or actions == "*" or (isinstance(actions, list) and "*" in actions):
                return {"*": ["*"]}
            raise ValueError("Wildcard module must map to ['*']")
        if module in PLATFORM_MODULES:
            if not allow_platform_modules:
                raise ValueError(
                    f"Platform module '{module}' cannot be granted on customer-tenant custom roles"
                )
        elif module not in SYSTEM_MODULES:
            if not _MODULE_KEY_RE.fullmatch(module):
                raise ValueError(f"Invalid permission module '{module}'")
            raise ValueError(f"Unknown permission module '{module}'")
        if isinstance(actions, str):
            action_list = [canonicalize_action(actions)]
        elif isinstance(actions, list):
            action_list = [canonicalize_action(a) for a in actions if str(a).strip()]
        elif dotted_actions is not None:
            # Dotted/colon key grants the parsed action; truthy scalar values are ignored
            action_list = []
        else:
            raise ValueError(f"Actions for module '{module}' must be a list")
        if dotted_actions is not None:
            action_list = list(dotted_actions) + action_list
        cleaned: list[str] = []
        for action in action_list:
            if action not in ALLOWED_ACTIONS:
                raise ValueError(f"Invalid action '{action}' for module '{module}'")
            if action == "*" and not allow_wildcard:
                raise ValueError("Custom roles cannot use wildcard '*' actions")
            if action not in cleaned:
                cleaned.append(action)
        if cleaned:
            _merge(module, cleaned)
    return out


def normalize_record_scope(value: str | None, *, default: str = "all") -> str:
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


def list_system_role_catalog() -> list[dict]:
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


def list_role_catalog() -> list[dict]:
    """Back-compat: system roles only. Prefer app.roles.list_role_catalog with tenant."""
    return list_system_role_catalog()


def serialize_user(user) -> dict:
    """Safe user payload — never include password hashes or TOTP secrets."""
    perms = user.permissions if isinstance(user.permissions, dict) and user.permissions else permissions_for_role(user.role)
    return {
        "id": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "role": user.role,
        "branch_id": getattr(user, "branch_id", None),
        "department_id": getattr(user, "department_id", None),
        "is_active": bool(user.is_active),
        "email_verified": bool(user.email_verified),
        "permissions": perms,
        "record_scope": record_scope_from_permissions(user.role, perms if isinstance(perms, dict) else None),
        "totp_enabled": bool(getattr(user, "totp_enabled", False)),
        "created_at": user.created_at,
    }


def has_permission(
    role: str,
    module: str,
    action: str,
    overrides: dict | None = None,
) -> bool:
    """Check module/action permission.

    When ``overrides`` is provided (typically ``user.permissions``), it is the
    authoritative map so custom roles cannot inherit cashier defaults by mistake.
    """
    action = canonicalize_action(action)
    if overrides is not None:
        # Stage 84 A1 — expand dotted/colon aliases before check
        perms = expand_permission_aliases(dict(overrides))
        if not perms:
            perms = {k: v for k, v in dict(overrides).items() if k != RECORD_SCOPE_KEY}
    else:
        perms = permissions_for_role(role)

    if perms.get("*") == ["*"] or "*" in (perms.get("*") or []):
        return True

    module_perms = perms.get(module) or []
    if isinstance(module_perms, str):
        module_perms = [canonicalize_action(module_perms)]
    else:
        module_perms = [canonicalize_action(a) for a in (module_perms or [])]
    if "*" in module_perms or action in module_perms:
        return True
    if action == "read" and "write" in module_perms:
        return True
    return False
