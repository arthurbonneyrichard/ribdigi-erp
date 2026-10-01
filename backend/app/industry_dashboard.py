"""Industry dashboard cards — existing ERP routes only.

Does not invent HIS, dispensing, hotel PMS, or other unimplemented verticals.
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
    {"id": "pos", "label": "POS", "href": "/pos", "module": "pos"},
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

# Restaurant: POS + printers (kitchen/bar already industry-gated on /printers). No PMS.
_RESTAURANT_FEATURES: tuple[dict[str, str], ...] = (
    {"id": "pos", "label": "POS", "href": "/pos", "module": "pos"},
    {"id": "printers", "label": "Printers", "href": "/printers", "module": "printers"},
)

_FEATURES: dict[str, tuple[dict[str, str], ...]] = {
    "pharmacy": _PHARMACY_FEATURES,
    "fmcg": _FMCG_FEATURES,
    "hotel": _HOTEL_FEATURES,
    "restaurant": _RESTAURANT_FEATURES,
}


def industry_home_path(industry: str | None) -> str:
    if canonicalize_industry(industry) == "hotel":
        return "/hotel"
    return "/dashboard"


def industry_dashboard_features(industry: str | None) -> list[dict[str, str]]:
    """Cards for the saved industry only. Empty for mart/retail (stock row only)."""
    ind = canonicalize_industry(industry)
    if not ind:
        return []
    return [dict(row) for row in _FEATURES.get(ind, ())]


def industry_dashboard_payload(tenant: Any) -> dict[str, Any]:
    raw = getattr(tenant, "industry", None) if tenant else None
    industry = canonicalize_industry(raw)
    enabled = set(resolve_enabled_modules(tenant) if tenant else [])
    features: list[dict[str, str]] = []
    for feat in industry_dashboard_features(industry):
        mod = (feat.get("module") or "").strip().lower()
        if mod in INDUSTRY_SPECIFIC_MODULES:
            if mod not in enabled:
                continue
            if not industry_allows_module(industry, mod):
                continue
        href = feat.get("href") or ""
        if industry != "hotel" and (href == "/hotel" or href.startswith("/hotel?")):
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
    }
