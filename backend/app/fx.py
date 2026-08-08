"""Multi-currency helpers: exchange rates and base-currency conversion."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def normalize_currency(code: str | None) -> str:
    cur = (code or "").strip().upper()
    if not cur or not _CURRENCY_RE.match(cur):
        raise HTTPException(status_code=400, detail="currency must be a 3-letter ISO code")
    return cur


def to_base(amount: float, rate: float) -> float:
    return round(float(amount or 0) * float(rate or 1), 2)


def doc_rate(obj) -> float:
    rate = float(getattr(obj, "exchange_rate", None) or 1)
    return rate if rate > 0 else 1.0


def doc_currency(obj, fallback: str = "GHS") -> str:
    cur = (getattr(obj, "currency", None) or "").strip().upper()
    return cur or fallback


async def get_base_currency(db: AsyncSession, tenant_id: str) -> str:
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one()
    return (tenant.currency or "GHS").strip().upper() or "GHS"


async def list_rates(db: AsyncSession, tenant_id: str) -> list[m.ExchangeRate]:
    return list(
        (
            await db.execute(
                select(m.ExchangeRate)
                .where(m.ExchangeRate.tenant_id == tenant_id)
                .order_by(m.ExchangeRate.currency_code)
            )
        )
        .scalars()
        .all()
    )


def serialize_rate(row: m.ExchangeRate) -> dict:
    return {
        "id": row.id,
        "currency_code": row.currency_code,
        "rate_to_base": float(row.rate_to_base),
        "source": getattr(row, "source", None) or "manual",
        "provider_fetched_at": getattr(row, "provider_fetched_at", None),
        "updated_at": row.updated_at,
        "created_at": row.created_at,
    }


async def upsert_rate(
    db: AsyncSession,
    *,
    tenant_id: str,
    currency_code: str,
    rate_to_base: float,
    source: str = "manual",
    provider_fetched_at: datetime | None = None,
) -> m.ExchangeRate:
    code = normalize_currency(currency_code)
    base = await get_base_currency(db, tenant_id)
    if code == base:
        raise HTTPException(status_code=400, detail="Cannot set a rate for the base currency")
    rate = float(rate_to_base)
    if rate <= 0:
        raise HTTPException(status_code=400, detail="rate_to_base must be positive")
    row = (
        await db.execute(
            select(m.ExchangeRate).where(
                m.ExchangeRate.tenant_id == tenant_id,
                m.ExchangeRate.currency_code == code,
            )
        )
    ).scalar_one_or_none()
    now = datetime.utcnow()
    if row:
        row.rate_to_base = rate
        row.source = source or "manual"
        if provider_fetched_at is not None:
            row.provider_fetched_at = provider_fetched_at
        row.updated_at = now
    else:
        row = m.ExchangeRate(
            tenant_id=tenant_id,
            currency_code=code,
            rate_to_base=rate,
            source=source or "manual",
            provider_fetched_at=provider_fetched_at,
        )
        db.add(row)
    await db.flush()
    return row


async def delete_rate(db: AsyncSession, tenant_id: str, currency_code: str) -> None:
    code = normalize_currency(currency_code)
    row = (
        await db.execute(
            select(m.ExchangeRate).where(
                m.ExchangeRate.tenant_id == tenant_id,
                m.ExchangeRate.currency_code == code,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Exchange rate not found")
    await db.delete(row)
    await db.flush()


async def resolve_rate(
    db: AsyncSession,
    tenant_id: str,
    currency: str | None,
    *,
    explicit_rate: float | None = None,
) -> tuple[str, float]:
    """Return (currency, rate_to_base). Base currency always rates at 1."""
    base = await get_base_currency(db, tenant_id)
    if currency is None or not str(currency).strip():
        return base, 1.0
    code = normalize_currency(currency)
    if code == base:
        return base, 1.0
    if explicit_rate is not None:
        rate = float(explicit_rate)
        if rate <= 0:
            raise HTTPException(status_code=400, detail="exchange_rate must be positive")
        return code, rate
    row = (
        await db.execute(
            select(m.ExchangeRate).where(
                m.ExchangeRate.tenant_id == tenant_id,
                m.ExchangeRate.currency_code == code,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(
            status_code=400,
            detail=f"No exchange rate configured for {code} (base {base})",
        )
    return code, float(row.rate_to_base)


def fx_lines_for_receipt(
    *,
    cash_base: float,
    ar_base: float,
    discount_base: float = 0.0,
) -> tuple[float, list[dict]]:
    """Return (fx_amount signed: +gain/-loss, extra journal lines for FX)."""
    # Dr Cash + Dr Discount = Cr AR + Cr FX(gain) | Dr FX(loss)
    plug = round(cash_base + discount_base - ar_base, 2)
    if abs(plug) < 0.005:
        return 0.0, []
    if plug > 0:
        return plug, [
            {
                "account_code": "4300",
                "debit": 0,
                "credit": plug,
                "description": "FX gain",
            }
        ]
    return plug, [
        {
            "account_code": "4300",
            "debit": abs(plug),
            "credit": 0,
            "description": "FX loss",
        }
    ]


def fx_lines_for_payment(
    *,
    cash_base: float,
    ap_base: float,
    discount_base: float = 0.0,
) -> tuple[float, list[dict]]:
    """Supplier pay: Dr AP = Cr Cash + Cr Disc + Cr FX(gain) | Dr FX(loss)."""
    # ap_base should equal cash_base + discount_base + fx_gain - fx_loss
    plug = round(ap_base - cash_base - discount_base, 2)
    if abs(plug) < 0.005:
        return 0.0, []
    if plug > 0:
        # AP cleared more than cash+disc → FX gain (we paid less in base)
        return plug, [
            {
                "account_code": "4300",
                "debit": 0,
                "credit": plug,
                "description": "FX gain",
            }
        ]
    return plug, [
        {
            "account_code": "4300",
            "debit": abs(plug),
            "credit": 0,
            "description": "FX loss",
        }
    ]


DEFAULT_WATCHLIST = ("USD", "EUR", "GBP")


async def _http_get_json(url: str) -> dict:
    import httpx
    from app.config import settings

    timeout = float(settings.FX_TIMEOUT_SECONDS or 15)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()


async def fetch_provider_rates(base_currency: str) -> tuple[str, dict[str, float]]:
    """Fetch live quotes. Returns (provider_name, {CODE: units_of_CODE_per_1_base})."""
    from app.config import settings

    provider = (settings.FX_PROVIDER or "open_er_api").strip().lower()
    if provider in {"disabled", "off", "none"}:
        raise HTTPException(status_code=503, detail="FX_PROVIDER is disabled")

    base = normalize_currency(base_currency)
    custom = (settings.FX_API_BASE_URL or "").strip().rstrip("/")

    if provider == "frankfurter":
        url = custom or "https://api.frankfurter.app"
        data = await _http_get_json(f"{url}/latest?from={base}")
        rates = {str(k).upper(): float(v) for k, v in (data.get("rates") or {}).items()}
        return "frankfurter", rates

    # Default: open.er-api.com (no key)
    url = custom or "https://open.er-api.com/v6"
    data = await _http_get_json(f"{url}/latest/{base}")
    result = str(data.get("result") or "").lower()
    if result == "error":
        raise HTTPException(
            status_code=502,
            detail=data.get("error-type") or data.get("message") or "FX provider error",
        )
    rates = {str(k).upper(): float(v) for k, v in (data.get("rates") or {}).items()}
    if not rates:
        raise HTTPException(status_code=502, detail="FX provider returned no rates")
    return "open_er_api", rates


def quotes_to_rate_to_base(quotes: dict[str, float], currency: str) -> float:
    """Convert provider quote (1 base = X foreign) → 1 foreign = rate_to_base base."""
    code = currency.upper()
    q = float(quotes.get(code) or 0)
    if q <= 0:
        raise HTTPException(status_code=502, detail=f"No live quote for {code}")
    return round(1.0 / q, 8)


async def refresh_tenant_rates(
    db: AsyncSession,
    *,
    tenant_id: str,
    currencies: list[str] | None = None,
    create_missing: bool = True,
) -> dict:
    """Pull live rates and upsert into tenant exchange_rates."""
    base = await get_base_currency(db, tenant_id)
    existing = await list_rates(db, tenant_id)
    watch: list[str] = []
    if currencies:
        watch = [normalize_currency(c) for c in currencies if c]
    else:
        watch = [r.currency_code for r in existing]
        if not watch and create_missing:
            watch = [c for c in DEFAULT_WATCHLIST if c != base]
    watch = [c for c in dict.fromkeys(watch) if c != base]
    if not watch:
        return {
            "base_currency": base,
            "provider": None,
            "updated": [],
            "skipped": [],
            "message": "No currencies to refresh",
        }

    provider, quotes = await fetch_provider_rates(base)
    fetched_at = datetime.utcnow()
    updated: list[dict] = []
    skipped: list[dict] = []
    for code in watch:
        if code not in quotes:
            skipped.append({"currency_code": code, "reason": "not_in_provider"})
            continue
        try:
            rate = quotes_to_rate_to_base(quotes, code)
            row = await upsert_rate(
                db,
                tenant_id=tenant_id,
                currency_code=code,
                rate_to_base=rate,
                source=provider,
                provider_fetched_at=fetched_at,
            )
            updated.append(serialize_rate(row))
        except HTTPException as exc:
            skipped.append({"currency_code": code, "reason": str(exc.detail)})
    return {
        "base_currency": base,
        "provider": provider,
        "fetched_at": fetched_at.isoformat() + "Z",
        "updated_count": len(updated),
        "skipped_count": len(skipped),
        "updated": updated,
        "skipped": skipped,
    }
