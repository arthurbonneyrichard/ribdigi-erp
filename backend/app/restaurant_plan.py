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

_COMPILED = [(key, re.compile(rule)) for key, spec in LOCKED_ON_STARTER.items() for rule in spec["rules"]]


def locked_feature(package_code: str | None, industry: str | None, action: str) -> str | None:
    """The locked feature key this ``METHOD /path`` action hits, or None when it is allowed."""
    if (package_code or "").strip().lower() != "starter":
        return None
    if (industry or "").strip().lower() != "restaurant":
        return None
    for key, rule in _COMPILED:
        if rule.fullmatch(action):
            return key
    return None


def starter_locks(package_code: str | None, industry: str | None) -> list[dict]:
    """Locked features for the Starter restaurant (empty on every other plan), for the UI."""
    if (package_code or "").strip().lower() != "starter" or (industry or "").strip().lower() != "restaurant":
        return []
    return [{"key": key, "label": spec["label"], "upgrade_to": "professional"} for key, spec in LOCKED_ON_STARTER.items()]


def upgrade_error(feature: str) -> HTTPException:
    label = LOCKED_ON_STARTER[feature]["label"]
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


def site_allowed(tenant) -> bool:
    """Public website and booking page: closed for a Starter restaurant."""
    return (getattr(tenant, "package_code", None) or "trial").strip().lower() != "starter"
