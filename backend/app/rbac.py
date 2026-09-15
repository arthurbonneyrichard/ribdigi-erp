"""Role and permission catalog for RIBDIGI ERP."""

from __future__ import annotations

import re
from copy import deepcopy

ROLE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "super_admin": {"*": ["*"]},
    "company_admin": {"*": ["*"]},
    # ADR-490 — tenant workspace administrators (no automatic company ops without membership+context)
    "tenant_owner": {
        "tenant_dashboard": ["read"],
        "companies": ["read", "write"],
        "subscription": ["read", "write"],
        "users": ["read", "write", "export"],
        "security": ["read", "write", "export"],
        "audit": ["read", "export"],
        "notifications": ["read", "write", "export"],
    },
    "tenant_admin": {
        "tenant_dashboard": ["read"],
        "companies": ["read", "write"],
        "subscription": ["read"],
        "users": ["read", "write", "export"],
        "security": ["read", "write", "export"],
        "audit": ["read", "export"],
        "notifications": ["read", "write", "export"],
    },
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
        # export: scoped CSV/report dumps allowed; view_cost withheld (COGS redacted).
        "dashboard": ["read", "export"],
        "inventory": ["read", "write", "export"],
        "sales": ["read", "write", "export"],
        "pos": ["read", "write", "export"],
        "purchasing": ["read", "write", "approve", "export"],
        "expenses": ["read", "write", "approve", "export"],
        "accounting": ["read", "export"],
        "credit": ["read", "write", "approve", "export"],
        "tax": ["read", "export"],
        "stores": ["read", "write", "export"],
        "reports": ["read", "export"],
        "notifications": ["read", "write", "export"],
        "users": ["read", "export"],
        "audit": ["read", "export"],
        "ai": ["read", "write", "export"],
        "business_insights": ["read", "write", "export"],
        "security": ["read", "write", "export"],
    },
    "sales_officer": {
        "dashboard": ["read", "export"],
        "inventory": ["read"],
        "sales": ["read", "write", "export"],
        "pos": ["read", "write", "export"],
        "credit": ["read", "write", "export"],
        "customers": ["read", "write", "export"],
        "reports": ["read", "export"],
        "notifications": ["read", "write", "export"],
        "ai": ["read"],
        "business_insights": ["read"],
        "security": ["read", "write", "export"],
    },
    "inventory_officer": {
        "dashboard": ["read", "export"],
        "inventory": ["read", "write", "export", "view_cost"],
        "purchasing": ["read", "write", "export", "view_cost"],
        "suppliers": ["read", "write", "export"],
        "reports": ["read", "export", "view_cost"],
        "notifications": ["read", "write", "export"],
        "ai": ["read"],
        "business_insights": ["read"],
        "security": ["read", "write", "export"],
    },
    "accountant": {
        "dashboard": ["read", "export"],
        "inventory": ["read", "export", "view_cost"],
        "sales": ["read", "export"],
        "purchasing": ["read", "export", "view_cost"],
        "expenses": ["read", "write", "approve", "export"],
        "accounting": ["read", "write", "export", "view_cost"],
        "credit": ["read", "write", "approve", "export"],
        "tax": ["read", "write", "export"],
        "reports": ["read", "export", "view_cost"],
        "notifications": ["read", "write", "export"],
        "ai": ["read"],
        "business_insights": ["read", "write", "export", "view_cost"],
        "audit": ["read", "export"],
        "security": ["read", "write", "export"],
    },
    "cashier": {
        "dashboard": ["read"],
        "inventory": ["read"],
        "pos": ["read", "write"],
        "sales": ["read"],
        "notifications": ["read", "write", "export"],
        "security": ["read", "write", "export"],
    },
}

ROLE_LABELS: dict[str, str] = {
    "super_admin": "Super Admin",
    "company_admin": "Tenant Admin",
    "tenant_owner": "Tenant Owner",
    "tenant_admin": "Tenant Administrator",
    "platform_super_admin": "Platform Super Admin",
    "platform_admin": "Platform Admin",
    "store_manager": "Store Manager",
    "sales_officer": "Sales Officer",
    "inventory_officer": "Inventory Officer",
    "accountant": "Accountant",
    "cashier": "Cashier",
}

# Stage 85 L1 — org-chart display names (slug unchanged; Manager ≡ store_manager)
ROLE_ORG_CHART_LABELS: dict[str, str] = {
    "company_admin": "Tenant Admin",
    "store_manager": "Manager",
    "cashier": "Cashier",
    "accountant": "Accountant",
    "inventory_officer": "Inventory Officer",
    "sales_officer": "Sales Officer",
    "super_admin": "Super Admin",
}

# Frontend nav href → required module (read). Used for menu filtering.
# Stage 95 N1 — Settings alias (/company) + Stores (/stores); deep-link query/hash
# paths resolve via pathname (Shell also allows sales|customers / purchasing|suppliers).
MENU_MODULE_BY_PATH: dict[str, str] = {
    "/dashboard": "dashboard",
    "/company": "company",  # Settings (MVP Navigation alias)
    "/inventory": "inventory",
    "/sales": "sales",
    "/pos": "pos",
    "/purchasing": "purchasing",
    "/expenses": "expenses",
    "/accounting": "accounting",
    "/credit": "credit",
    "/tax": "tax",
    "/stores": "stores",  # Stores + Warehouse discoverability
    "/reports": "reports",
    "/notifications": "notifications",
    "/audit": "audit",
    "/activity": "audit",
    "/backup": "backup",
    "/security": "security",
    "/ai": "ai",
    "/business-insights": "business_insights",
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
        "business_insights",
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
# First-class actions: read/write/approve plus export (CSV/dumps) and view_cost (COGS/margin).
ALLOWED_ACTIONS = frozenset({"read", "write", "approve", "export", "view_cost", "*"})
_MODULE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
# Stage 84 A1 — common dotted/colon aliases → canonical actions
_ACTION_ALIASES = {
    "view": "read",
    "edit": "write",
    "update": "write",
    "create": "write",
    "delete": "write",
    "cost": "view_cost",
    "viewcost": "view_cost",
    "csv": "export",
    "download": "export",
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
    "tenant_owner": "all",
    "tenant_admin": "all",
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
                "org_chart_label": ROLE_ORG_CHART_LABELS.get(
                    role, ROLE_LABELS.get(role, role)
                ),
                "permissions": permissions_for_role(role),
                "record_scope": record_scope_for_role(role),
                "system": True,
            }
        )
    return rows


def list_role_catalog() -> list[dict]:
    """Back-compat: system roles only. Prefer app.roles.list_role_catalog with tenant."""
    return list_system_role_catalog()


def serialize_user(user, *, include_permissions: bool = True) -> dict:
    """Safe user payload — never include password hashes or TOTP secrets.

    When ``include_permissions`` is False (store_manager users list/get), omit the
    permission matrix and record_scope so staff lookup does not dump role catalogs.
    Callers may further redact email/phone, branch_id/department_id,
    ``totp_enabled``, and ``email_verified`` via ``redact_user_contact_pii``.
    """
    payload = {
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
        "totp_enabled": bool(getattr(user, "totp_enabled", False)),
        "created_at": user.created_at,
    }
    if include_permissions:
        perms = (
            user.permissions
            if isinstance(user.permissions, dict) and user.permissions
            else permissions_for_role(user.role)
        )
        payload["permissions"] = perms
        payload["record_scope"] = record_scope_from_permissions(
            user.role, perms if isinstance(perms, dict) else None
        )
    return payload


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


# --- RBAC hardening helpers (extend existing engine; do not replace) ---

# Roles whose last active holder must not be deactivated/demoted (owner lockout).
PROTECTED_OWNER_ROLES = frozenset({"super_admin", "tenant_owner"})
# When no protected owner remains, last active company_admin is also protected.
FALLBACK_ADMIN_ROLES = frozenset({"company_admin"})

# Modules that warrant an admin-UI / API warning when granted on custom roles.
DANGEROUS_PERMISSION_MODULES = frozenset(
    {
        "users",
        "backup",
        "audit",
        "accounting",
        "credit",
        "security",
        "companies",
        "subscription",
        "platform_tenants",
        "platform_users",
        "platform_plans",
        "platform_billing",
        "platform_settings",
        "platform_audit",
    }
)

_DANGEROUS_MODULE_REASONS: dict[str, str] = {
    "users": "Can create users, assign roles, and escalate privileges.",
    "backup": "Can export or restore tenant data backups.",
    "audit": "Can read sensitive security/audit trails.",
    "accounting": "Can view or alter financial ledgers and journals.",
    "credit": "Can change credit limits and approve credit risk actions.",
    "security": "Can manage MFA/session security settings.",
    "companies": "Can create/alter companies and store allocations.",
    "subscription": "Can alter tenant subscription entitlements.",
    "platform_tenants": "Platform-wide tenant administration.",
    "platform_users": "Platform-wide user administration.",
    "platform_plans": "Platform plan catalog administration.",
    "platform_billing": "Platform billing administration.",
    "platform_settings": "Platform settings administration.",
    "platform_audit": "Platform audit trail access.",
}


def is_wildcard_admin(permissions: dict | None) -> bool:
    if not isinstance(permissions, dict):
        return False
    star = permissions.get("*") or []
    if isinstance(star, str):
        star = [star]
    return star == ["*"] or "*" in list(star)


_IMPLIES_READ = frozenset({"write", "approve", "export", "view_cost", "*"})


def ensure_permission_dependencies(
    raw: dict | None,
    *,
    allow_wildcard: bool = False,
    allow_platform_modules: bool = False,
) -> dict[str, list[str]]:
    """Normalize map and ensure write/approve/export/view_cost imply stored ``read``.

    Raises ValueError on invalid input (via normalize_permissions_map).
    """
    perms = normalize_permissions_map(
        raw,
        allow_wildcard=allow_wildcard,
        allow_platform_modules=allow_platform_modules,
    )
    if is_wildcard_admin(perms):
        return perms
    out: dict[str, list[str]] = {}
    for module, actions in perms.items():
        acts = [canonicalize_action(a) for a in (actions or [])]
        cleaned: list[str] = []
        for a in acts:
            if a not in cleaned:
                cleaned.append(a)
        if any(a in _IMPLIES_READ for a in cleaned) and "read" not in cleaned:
            cleaned.insert(0, "read")
        if cleaned:
            out[module] = cleaned
    return out


def validate_permission_dependencies(raw: dict | None) -> list[str]:
    """Return human-readable dependency issues without mutating (pre-check)."""
    if not isinstance(raw, dict):
        return []
    issues: list[str] = []
    for key, actions in raw.items():
        module, dotted = _split_permission_key(str(key or ""))
        if not module or module == RECORD_SCOPE_KEY or module == "*":
            continue
        if isinstance(actions, str):
            acts = [canonicalize_action(actions)]
        elif isinstance(actions, list):
            acts = [canonicalize_action(a) for a in actions if str(a).strip()]
        else:
            acts = []
        if dotted:
            acts = list(dotted) + acts
        if any(a in _IMPLIES_READ for a in acts) and "read" not in acts:
            issues.append(
                f"Module '{module}': write/approve/export/view_cost requires read "
                "(will be auto-added on save)"
            )
    return issues


def claims_has_permission(claims: dict | None, module: str, action: str) -> bool:
    """Check module/action against JWT/API claims (role + permissions overrides)."""
    if not isinstance(claims, dict):
        return False
    role = claims.get("role") or ""
    overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    return has_permission(role, module, action, overrides=overrides)


def permissions_within_grantor(
    candidate: dict | None,
    grantor: dict | None,
) -> list[str]:
    """Return modules/actions in candidate not held by grantor.

    Wildcard grantors (`*:*`) may grant any non-platform-blocked module already
    accepted by ``normalize_permissions_map``.
    """
    if is_wildcard_admin(grantor):
        return []
    cand = expand_permission_aliases(candidate or {})
    grant = expand_permission_aliases(grantor or {})
    missing: list[str] = []
    for module, actions in cand.items():
        if module == RECORD_SCOPE_KEY:
            continue
        for action in actions or []:
            action = canonicalize_action(action)
            if not has_permission("cashier", module, action, overrides=grant):
                missing.append(f"{module}:{action}")
    return missing


def assert_permissions_within_grantor(candidate: dict | None, grantor: dict | None) -> None:
    missing = permissions_within_grantor(candidate, grantor)
    if missing:
        raise ValueError(
            "Cannot grant permissions beyond your authority: " + ", ".join(sorted(missing))
        )


def dangerous_permission_warnings(raw: dict | None) -> list[dict]:
    """Structured warnings for dangerous modules present in a permission map."""
    if not isinstance(raw, dict):
        return []
    expanded = expand_permission_aliases(raw)
    warnings: list[dict] = []
    for module in sorted(expanded.keys()):
        if module not in DANGEROUS_PERMISSION_MODULES:
            continue
        actions = expanded.get(module) or []
        if not actions:
            continue
        warnings.append(
            {
                "module": module,
                "actions": list(actions),
                "severity": "high" if module in {"users", "backup", "subscription"} else "elevated",
                "message": _DANGEROUS_MODULE_REASONS.get(
                    module, f"Sensitive module '{module}' granted."
                ),
            }
        )
    return warnings

