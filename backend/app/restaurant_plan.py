"""Which restaurant features the Starter package leaves switched off.

Starter keeps the till, shifts, kitchen, floor, bookings taken by staff, recipes, waste, books and HR.
Professional, Enterprise and the free trial keep everything. A locked feature answers 403
``PACKAGE_UPGRADE_REQUIRED`` with the feature name and the plan to move to. Reading is never blocked
(a Starter owner can still see what they would get); only changes, actions and the public site are.
"""

from __future__ import annotations

import re

from fastapi import Depends, HTTPException, Request

from app.security import current_claims

LOCKED_ON_STARTER: dict[str, dict] = {
    "website": {
        "label": "Live website, online ordering and online booking",
        "rules": (r"(PUT|POST|PATCH|DELETE) /restaurant/(booking-link|online-orders)",),
    },
    "alerts": {
        "label": "Order and booking alerts (email and WhatsApp)",
        "rules": (
            r"(PUT|POST|PATCH|DELETE) /restaurant/alerts(/test)?",
            r"(PUT|POST|PATCH|DELETE) /online-alerts(/test)?",
        ),
    },
    "delivery": {
        "label": "Delivery zones, riders and Mobile Money prompts",
        "rules": (
            r"(PUT|POST|PATCH|DELETE) /restaurant/delivery-zones",
            r"POST /restaurant/orders/[^/]+/(rider|dispatch|delivered)",
            r"POST /restaurant/till/momo(/[^/]+/otp)?",
        ),
    },
    "guest_growth": {
        "label": "Gift cards, loyalty points, happy hours and tips share-out",
        "rules": (
            r"POST /restaurant/gift-cards",
            r"PUT /restaurant/happy-hours",
            r"POST /restaurant/orders/[^/]+/guest",
            r"(POST|PUT|PATCH|DELETE) /restaurant/tips(/.*)?",
        ),
    },
}

# Retail and wholesale (the retail desk): what Starter leaves off. Same Pro+ rule as the restaurant.
LOCKED_ON_STARTER_RETAIL: dict[str, dict] = {
    "gift_loyalty": {
        "label": "Gift cards and loyalty points",
        "rules": (r"POST /gift-cards", r"POST /customers/[^/]+/loyalty"),
    },
    "momo_prompts": {
        "label": "Mobile Money prompts",
        "rules": (r"POST /pos/momo(/[^/]+/otp)?",),
    },
    "held_layaway": {
        "label": "Held sales and layaway",
        "rules": (r"POST /pos/held(/[^/]+/take)?", r"POST /pos/layaways(/[^/]+/(payments|cancel))?"),
    },
    "serials": {
        "label": "Serial-number tracking",
        "rules": (),
    },
}
RETAIL_INDUSTRIES = frozenset({"retail", "wholesale"})
_ALL_LOCKS = {"restaurant": LOCKED_ON_STARTER, "retail": LOCKED_ON_STARTER_RETAIL}


def _desk(industry: str | None) -> str | None:
    value = (industry or "").strip().lower()
    if value == "restaurant":
        return "restaurant"
    if value in RETAIL_INDUSTRIES:
        return "retail"
    return None


_COMPILED = [
    (key, re.compile(rule), desk)
    for desk, locks in _ALL_LOCKS.items()
    for key, spec in locks.items()
    for rule in spec["rules"]
]


def locked_feature(package_code: str | None, industry: str | None, action: str) -> str | None:
    """The locked feature key this ``METHOD /path`` action hits, or None when it is allowed."""
    if (package_code or "").strip().lower() != "starter":
        return None
    desk = _desk(industry)
    if desk is None:
        return None
    for key, rule, rule_desk in _COMPILED:
        if rule_desk == desk and rule.fullmatch(action):
            return key
    return None


def starter_locks(package_code: str | None, industry: str | None) -> list[dict]:
    """Locked features for the Starter restaurant (empty on every other plan), for the UI."""
    desk = _desk(industry)
    if (package_code or "").strip().lower() != "starter" or desk is None:
        return []
    return [{"key": key, "label": spec["label"], "upgrade_to": "professional"} for key, spec in _ALL_LOCKS[desk].items()]


def upgrade_error(feature: str) -> HTTPException:
    label = (LOCKED_ON_STARTER.get(feature) or LOCKED_ON_STARTER_RETAIL[feature])["label"]
    return HTTPException(
        status_code=403,
        detail={
            "code": "PACKAGE_UPGRADE_REQUIRED",
            "message": f"{label} is not included in the Starter package. Upgrade to Professional to use it.",
            "feature": feature,
            "upgrade_to": "professional",
        },
    )


async def restaurant_package_gate(request: Request, claims: dict = Depends(current_claims)) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    path = request.url.path
    if path.startswith("/api/v1"):
        path = path[len("/api/v1") :]
    action = f"{request.method} {path.rstrip('/') or '/'}"
    feature = locked_feature(claims.get("package_code"), claims.get("industry"), action)
    if feature:
        raise upgrade_error(feature)


def require_serials_allowed(claims: dict) -> None:
    """Serial-number tracking is Professional and up on the retail desk."""
    if _desk(claims.get("industry")) == "retail" and (claims.get("package_code") or "").strip().lower() == "starter":
        raise upgrade_error("serials")


def site_allowed(tenant) -> bool:
    """Public website and booking page: closed for a Starter restaurant."""
    return (getattr(tenant, "package_code", None) or "trial").strip().lower() != "starter"
