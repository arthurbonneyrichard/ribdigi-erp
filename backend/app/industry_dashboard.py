"""Industry dashboard cards — existing ERP routes only.

Does not invent HIS, gift cards, or hotel PMS for trade tenants.
Industry is always taken from the tenant record (see ``build_dashboard``).
"""

from __future__ import annotations

from typing import Any

from app.packages import (
    INDUSTRY_SPECIFIC_MODULES,
    canonicalize_industry,
    industry_allows_module,
    resolve_enabled_modules,
)

# Pharmacy extras: lots/batches plus catalog Rx/dosage and Rx records.
# Mart/retail keep the generic Products → Low stock → Out of stock → Expiring soon row.
_PHARMACY_FEATURES: tuple[dict[str, str], ...] = (
    {
        "id": "expiry_lots",
        "label": "Expiring lots",
        "href": "/inventory?tab=expiry",
        "module": "inventory",
    },
    {
        "id": "batches",
        "label": "Batches",
        "href": "/inventory?tab=batches",
        "module": "inventory",
    },
    {
        "id": "rx_products",
        "label": "Rx-only products",
        "href": "/inventory?tab=products&rx=1",
        "module": "inventory",
    },
    {
        "id": "prescriptions",
        "label": "Prescriptions",
        "href": "/prescriptions",
        "module": "inventory",
    },
)

_FMCG_FEATURES: tuple[dict[str, str], ...] = (
    {"id": "fmcg_home", "label": "FMCG overview", "href": "/fmcg", "module": "fmcg"},
    {
        "id": "fmcg_schemes",
        "label": "Trade schemes",
        "href": "/fmcg?tab=schemes",
        "module": "fmcg",
    },
    {"id": "fmcg_routes", "label": "Routes", "href": "/fmcg?tab=routes", "module": "fmcg"},
    {
        "id": "fmcg_deliveries",
        "label": "Deliveries",
        "href": "/fmcg?tab=deliveries",
        "module": "fmcg",
    },
    {
        "id": "fmcg_packs",
        "label": "Pack convert",
        "href": "/fmcg?tab=packs",
        "module": "fmcg",
    },
)

_HOTEL_FEATURES: tuple[dict[str, str], ...] = (
    {"id": "hotel_home", "label": "Hotel dashboard", "href": "/hotel", "module": "hotel"},
    {
        "id": "hotel_reservations",
        "label": "Reservations",
        "href": "/hotel?tab=reservations",
        "module": "hotel",
    },
    {
        "id": "hotel_front_desk",
        "label": "Front desk",
        "href": "/hotel?tab=front-desk",
        "module": "hotel",
    },
)

# Restaurant floor, kitchen, and printers. Hotel rooms stay off this list.
_RESTAURANT_FEATURES: tuple[dict[str, str], ...] = (
    {"id": "restaurant_home", "label": "Restaurant dashboard", "href": "/restaurant", "module": "restaurant"},
    {"id": "restaurant_orders", "label": "Orders", "href": "/restaurant?tab=orders", "module": "restaurant"},
    {"id": "restaurant_kitchen", "label": "Kitchen", "href": "/restaurant?tab=kitchen", "module": "restaurant"},
    {"id": "printers", "label": "Printers", "href": "/printers", "module": "printers"},
)

_RETAIL_FEATURES: tuple[dict[str, str], ...] = ()

_WHOLESALE_FEATURES: tuple[dict[str, str], ...] = (
    {"id": "quotes", "label": "Quotations", "href": "/sales?tab=quotations", "module": "sales"},
    {"id": "orders", "label": "Sales orders", "href": "/sales?tab=orders", "module": "sales"},
    {"id": "credit", "label": "B2B credit", "href": "/credit", "module": "credit"},
)

_RETAIL_WHOLESALE_FEATURES: tuple[dict[str, str], ...] = (
    {"id": "quotes", "label": "Wholesale quotes", "href": "/sales?tab=quotations", "module": "sales"},
    {"id": "orders", "label": "Wholesale orders", "href": "/sales?tab=orders", "module": "sales"},
    {"id": "credit", "label": "B2B credit", "href": "/credit", "module": "credit"},
)

_HOSPITAL_FEATURES: tuple[dict[str, str], ...] = (
    {"id": "hospital_home", "label": "Patients and visits", "href": "/hospital", "module": "hospital"},
)

# Industries with a real operations dashboard. Stored types outside this set
# (mart, bakery, distribution, general trading, manufacturing) and blank or
# unknown values stay unconfigured — they do not inherit the retail desk.
CONFIGURED_DASHBOARD_INDUSTRIES: frozenset[str] = frozenset(
    {"retail", "hotel", "restaurant", "pharmacy"}
)

_FEATURES: dict[str, tuple[dict[str, str], ...]] = {
    "retail": _RETAIL_FEATURES,
    "hotel": _HOTEL_FEATURES,
    "restaurant": _RESTAURANT_FEATURES,
    "pharmacy": _PHARMACY_FEATURES,
}


def _raw_industry(industry: str | None) -> str:
    return str(industry or "").strip().lower().replace(" ", "_").replace("-", "_")


def is_software_owner_industry(industry: str | None) -> bool:
    """Ribdigi House workspace. Not a customer operating industry."""
    return _raw_industry(industry) == "software"


def dashboard_layout(industry: str | None) -> str:
    """Server-side layout key. Never treats a missing industry as retail."""
    if is_software_owner_industry(industry):
        return "platform"
    ind = canonicalize_industry(industry)
    if not ind or ind not in CONFIGURED_DASHBOARD_INDUSTRIES:
        return "unconfigured"
    return ind


def shows_retail_operations(industry: str | None) -> bool:
    """Retail KPI grid is only the retail desk."""
    return dashboard_layout(industry) == "retail"


def industry_home_path(industry: str | None) -> str:
    if is_software_owner_industry(industry):
        return "/platform"
    ind = canonicalize_industry(industry)
    if ind == "hotel":
        return "/hotel"
    if ind == "restaurant":
        return "/restaurant"
    return "/dashboard"


# A restaurant rings on its own till (/restaurant/till/*, restaurant orders), never the retail POS.
POS_INDUSTRIES = frozenset({"retail", "hotel", "pharmacy"})


def assert_pos_for_industry(claims: dict) -> None:
    """POS is a storefront for retail and hotel. Other industries (restaurant included) get 403."""
    from fastapi import HTTPException

    from app.rbac import is_platform_role

    if is_platform_role(claims.get("role")):
        return
    industry = canonicalize_industry(claims.get("industry"))
    if industry in POS_INDUSTRIES:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "INDUSTRY_MODULE_DISABLED",
            "message": "This feature is not available for this company.",
            "module": "pos",
            "industry": industry,
        },
    )


def assert_gift_cards_for_industry(claims: dict) -> None:
    """Gift cards are a retail storefront. Other industries get 403."""
    from fastapi import HTTPException

    from app.rbac import is_platform_role

    if is_platform_role(claims.get("role")):
        return
    industry = canonicalize_industry(claims.get("industry"))
    if industry == "retail":
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "INDUSTRY_MODULE_DISABLED",
            "message": "This feature is not available for this company.",
            "module": "pos",
            "industry": industry,
        },
    )


def industry_dashboard_features(industry: str | None) -> list[dict[str, str]]:
    """Cards for the saved industry only. Mart keeps the stock row only."""
    ind = canonicalize_industry(industry)
    if not ind:
        return []
    return [dict(row) for row in _FEATURES.get(ind, ())]


def industry_dashboard_payload(tenant: Any) -> dict[str, Any]:
    raw = getattr(tenant, "industry", None) if tenant else None
    if is_software_owner_industry(raw):
        return {
            "industry": "software",
            "industry_home": "/platform",
            "industry_features": [],
            "dashboard_layout": "platform",
            "show_retail_operations": False,
        }
    industry = canonicalize_industry(raw)
    enabled = set(resolve_enabled_modules(tenant) if tenant else [])
    features: list[dict[str, str]] = []
    for feat in industry_dashboard_features(industry):
        mod = (feat.get("module") or "").strip().lower()
        if mod and mod not in enabled:
            continue
        if mod in INDUSTRY_SPECIFIC_MODULES:
            if not industry_allows_module(industry, mod):
                continue
        href = feat.get("href") or ""
        if industry != "hotel" and (href == "/hotel" or href.startswith("/hotel?")):
            continue
        if industry != "restaurant" and (href == "/restaurant" or href.startswith("/restaurant?")):
            continue
        if industry != "fmcg" and (href == "/fmcg" or href.startswith("/fmcg?")):
            continue
        if industry != "hospital" and (href == "/hospital" or href.startswith("/hospital?")):
            continue
        if industry != "pharmacy" and (
            href == "/prescriptions" or href.startswith("/prescriptions?")
        ):
            continue
        features.append(feat)
    return {
        "industry": industry,
        "industry_home": industry_home_path(industry),
        "industry_features": features,
        "dashboard_layout": dashboard_layout(industry),
        "show_retail_operations": shows_retail_operations(industry),
    }
