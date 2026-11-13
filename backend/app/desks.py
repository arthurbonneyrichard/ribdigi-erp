"""The desks RIBDIGI sells. Each one can keep its data in its own database.

A company belongs to one desk, decided by its business type. `DESK_DATABASE_URLS` says which
database a desk uses. A desk with no entry uses DATABASE_URL, so with nothing set the whole
system runs on one database exactly as before.
"""

from __future__ import annotations

import json

from app.config import settings

DESKS: tuple[str, ...] = ("retail", "hotel", "restaurant", "bakery", "fmcg", "gym", "hrm")

# Older business types with no desk of their own.
_DESK_OF_INDUSTRY = {"pharmacy": "retail", "hospital": "retail", "wholesale": "retail"}


def desk_for_industry(industry: str | None) -> str:
    key = str(industry or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in DESKS:
        return key
    return _DESK_OF_INDUSTRY.get(key, "retail")


def desk_urls() -> dict[str, str]:
    """Only the desks that have their own database."""
    raw = (settings.DESK_DATABASE_URLS or "").strip()
    if not raw:
        return {}
    urls = json.loads(raw)
    unknown = sorted(set(urls) - set(DESKS))
    if unknown:
        raise ValueError(f"DESK_DATABASE_URLS names unknown desks: {', '.join(unknown)}")
    return {desk: str(url) for desk, url in urls.items() if str(url).strip()}


def separate_databases() -> bool:
    return bool(desk_urls())
