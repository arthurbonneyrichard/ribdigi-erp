"""Resolve fixed and percent discounts for sales/POS lines and headers."""

from __future__ import annotations

from fastapi import HTTPException

from app.honesty import money_json

ALLOWED_TYPES = frozenset({"fixed", "percent"})


def normalize_discount_type(value: object) -> str:
    raw = str(value or "fixed").strip().lower()
    if raw not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Discount type must be fixed or percent")
    return raw


def resolve_discount(
    *,
    base_amount: float,
    discount: float = 0,
    discount_type: str | None = "fixed",
    discount_percent: float = 0,
    label: str = "Discount",
) -> tuple[float, str, float]:
    """Return (amount, type, percent) with amount clamped to the base and never above it."""
    dtype = normalize_discount_type(discount_type)
    base = money_json(base_amount or 0)
    if base < 0:
        raise HTTPException(status_code=400, detail=f"{label} base cannot be negative")
    pct = money_json(discount_percent or 0)
    if pct < 0 or pct > 100:
        raise HTTPException(status_code=400, detail=f"{label} percent must be between 0 and 100")
    if dtype == "percent":
        amount = money_json(round(base * pct / 100.0, 2))
    else:
        amount = money_json(discount or 0)
        pct = money_json(0) if amount <= 0 else pct
    if amount < 0:
        raise HTTPException(status_code=400, detail=f"{label} must be 0 or greater")
    if amount > base + 1e-9:
        raise HTTPException(status_code=400, detail=f"{label} cannot exceed the amount")
    return amount, dtype, pct
