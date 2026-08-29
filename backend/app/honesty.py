"""Shared OpenAPI honesty helpers (service defense-in-depth + response money JSON).

Request schemas already reject blank/URL/punctuation narratives with **422**.
Services historically only `.strip()`-checked emptiness → **400**. These helpers
mirror the letter/digit + no `://`/`@` honesty so direct/service callers cannot
persist garbage when the OpenAPI layer is bypassed.

Response serializers historically used bare `float(orm_decimal)`. `money_json`
is the Decimal→JSON-number pilot: finite float for `env()` bodies (not decimal
strings; NaN/Inf rejected).
"""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any

from fastapi import HTTPException


def require_honest_narrative(
    value: str | None,
    *,
    label: str,
    min_length: int = 1,
    max_length: int = 500,
) -> str:
    """Strip + narrative honesty; blank/URL/garbage → **400**.

    Mirrors OpenAPI `*ReasonValue` / narrative Values (422 at schema).
    """
    text = (value or "").strip()
    if not text or len(text) < min_length or len(text) > max_length:
        raise HTTPException(status_code=400, detail=f"{label} is required")
    if "://" in text or "@" in text:
        raise HTTPException(status_code=400, detail=f"{label} must be a plain narrative")
    if not re.search(r"[A-Za-z0-9]", text):
        raise HTTPException(status_code=400, detail=f"{label} must be a plain narrative")
    return text


def money_json(value: Any, *, default: float = 0.0) -> float:
    """Convert Decimal / numeric / None to a finite JSON number for responses.

    ORM money columns are Numeric/Decimal; API responses use JSON **numbers**
    (IEEE-754 doubles), not decimal strings. Rejects NaN/Inf.
    """
    if value is None:
        out = float(default)
    elif isinstance(value, bool):
        raise TypeError("bool is not a money value")
    elif isinstance(value, Decimal):
        out = float(value)
    else:
        out = float(value)
    if not math.isfinite(out):
        raise ValueError("money value must be finite")
    return out
