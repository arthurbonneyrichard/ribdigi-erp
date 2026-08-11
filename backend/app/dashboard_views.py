"""Role- and permission-scoped tenant dashboard views (Stage 80 T1)."""

from __future__ import annotations

from app.rbac import has_permission

# KPI / section keys → required (module, action)
SECTION_PERMISSIONS: dict[str, tuple[str, str]] = {
    "sales": ("sales", "read"),
    "pos": ("pos", "read"),
    "purchasing": ("purchasing", "read"),
    "expenses": ("expenses", "read"),
    "accounting": ("accounting", "read"),
    "inventory": ("inventory", "read"),
    "credit": ("credit", "read"),
    "customers": ("sales", "read"),
    "suppliers": ("purchasing", "read"),
    "reports": ("reports", "read"),
    "users": ("users", "read"),
    "charts_revenue": ("dashboard", "read"),
}

# Payload fields belonging to each section
SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "sales": (
        "total_sales",
        "daily_revenue",
        "yesterday_revenue",
        "dod_change_pct",
        "monthly_revenue",
        "prior_month_revenue",
        "mom_change_pct",
        "recent_sales",
        "top_products",
        "daily_revenue_series",
        "monthly_revenue_series",
    ),
    "purchasing": ("total_purchases",),
    "expenses": ("total_expenses",),
    "inventory": ("products", "low_stock", "out_of_stock", "expiring_batches"),
    "customers": ("customers",),
    "suppliers": ("suppliers",),
    "users": ("user_stats",),
    "charts_revenue": ("daily_revenue_series", "monthly_revenue_series"),
}


def dashboard_view_for_role(role: str) -> str:
    role = (role or "").strip().lower()
    if role == "cashier":
        return "cashier"
    if role == "store_manager":
        return "store_manager"
    if role in {"company_admin", "super_admin", "accountant"}:
        return "executive"
    return "executive"


def allowed_sections(claims: dict) -> list[str]:
    role = claims.get("role") or "cashier"
    perms = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    out: list[str] = []
    for section, (module, action) in SECTION_PERMISSIONS.items():
        if has_permission(role, module, action, overrides=perms):
            out.append(section)
    # Cashier view: never expose purchasing/accounting/expenses/users/suppliers even if misconfigured
    view = dashboard_view_for_role(role)
    if view == "cashier":
        blocked = {"purchasing", "expenses", "accounting", "users", "suppliers", "credit", "reports"}
        out = [s for s in out if s not in blocked]
    return out


def filter_dashboard_payload(payload: dict, claims: dict) -> dict:
    """Return a copy of payload with disallowed sections removed."""
    sections = allowed_sections(claims)
    allowed = set(sections)
    keep_fields: set[str] = {"view", "sections", "kpi_links", "role_label", "store_scope"}
    for section in sections:
        keep_fields.update(SECTION_FIELDS.get(section, ()))
    # Always keep dashboard-level identity metadata
    filtered = {k: v for k, v in payload.items() if k in keep_fields}
    # Prune kpi_links to visible keys
    links = payload.get("kpi_links") or {}
    if isinstance(links, dict):
        filtered["kpi_links"] = {k: v for k, v in links.items() if k in filtered or k in keep_fields}
    filtered["view"] = dashboard_view_for_role(claims.get("role") or "")
    filtered["sections"] = sections
    return filtered
