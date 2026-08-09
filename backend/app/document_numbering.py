"""Tenant-configurable document number prefix + series (BR-7.4 / BR-20.4)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

DOC_KEYS = (
    "sales_invoice",
    "purchase_invoice",
    "purchase_order",
    "goods_receipt",
    "sales_quotation",
    "sales_order",
    "sales_return",
)

DEFAULTS: dict[str, dict] = {
    "sales_invoice": {"prefix": "INV", "include_year": True, "pad": 4, "next_number": 1},
    "purchase_invoice": {"prefix": "PINV", "include_year": True, "pad": 4, "next_number": 1},
    "purchase_order": {"prefix": "PO", "include_year": True, "pad": 4, "next_number": 1},
    "goods_receipt": {"prefix": "GRN", "include_year": True, "pad": 4, "next_number": 1},
    "sales_quotation": {"prefix": "QT", "include_year": True, "pad": 4, "next_number": 1},
    "sales_order": {"prefix": "SO", "include_year": True, "pad": 4, "next_number": 1},
    "sales_return": {"prefix": "SR", "include_year": True, "pad": 4, "next_number": 1},
}


def _normalize_series(raw: dict | None, defaults: dict) -> dict:
    src = raw if isinstance(raw, dict) else {}
    prefix = str(src.get("prefix") if src.get("prefix") is not None else defaults["prefix"]).strip().upper()
    if not prefix or len(prefix) > 20:
        raise HTTPException(status_code=400, detail="document prefix must be 1–20 characters")
    for ch in prefix:
        if not (ch.isalnum() or ch in {"-", "_"}):
            raise HTTPException(
                status_code=400,
                detail="document prefix may only contain letters, digits, hyphen, underscore",
            )
    include_year = bool(src["include_year"]) if "include_year" in src else bool(defaults["include_year"])
    try:
        pad = int(src["pad"]) if "pad" in src else int(defaults["pad"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="pad must be an integer") from exc
    if pad < 1 or pad > 12:
        raise HTTPException(status_code=400, detail="pad must be between 1 and 12")
    try:
        next_number = (
            int(src["next_number"]) if "next_number" in src else int(defaults["next_number"])
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="next_number must be an integer") from exc
    if next_number < 1:
        raise HTTPException(status_code=400, detail="next_number must be >= 1")
    return {
        "prefix": prefix,
        "include_year": include_year,
        "pad": pad,
        "next_number": next_number,
    }


def normalize_document_numbering(raw: dict | None) -> dict:
    src = raw if isinstance(raw, dict) else {}
    out: dict[str, dict] = {}
    for key in DOC_KEYS:
        out[key] = _normalize_series(src.get(key), DEFAULTS[key])
    return out


def format_document_number(series: dict, *, number: int | None = None, when: datetime | None = None) -> str:
    cfg = _normalize_series(series, series)
    n = int(number if number is not None else cfg["next_number"])
    body = str(n).zfill(int(cfg["pad"]))
    if cfg["include_year"]:
        year = (when or datetime.utcnow()).year
        return f"{cfg['prefix']}-{year}-{body}"
    return f"{cfg['prefix']}-{body}"


def preview_document_numbering(raw: dict | None, *, when: datetime | None = None) -> dict[str, str]:
    cfg = normalize_document_numbering(raw)
    return {key: format_document_number(series, when=when) for key, series in cfg.items()}


async def get_tenant_for_numbering(db: AsyncSession, tenant_id: str) -> m.Tenant:
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id).with_for_update())
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


async def allocate_document_number(
    db: AsyncSession,
    *,
    tenant_id: str,
    doc_key: str,
    when: datetime | None = None,
) -> str:
    if doc_key not in DOC_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown document type: {doc_key}")
    tenant = await get_tenant_for_numbering(db, tenant_id)
    cfg = normalize_document_numbering(getattr(tenant, "document_numbering", None))
    series = cfg[doc_key]
    number = int(series["next_number"])
    doc_number = format_document_number(series, number=number, when=when)
    series["next_number"] = number + 1
    cfg[doc_key] = series
    tenant.document_numbering = cfg
    await db.flush()
    return doc_number


def merge_document_numbering(existing: dict | None, patch: dict | None) -> dict:
    """Merge partial settings updates; only provided keys/fields change."""
    base = normalize_document_numbering(existing)
    if not patch:
        return base
    if not isinstance(patch, dict):
        raise HTTPException(status_code=400, detail="document_numbering must be an object")
    for key, value in patch.items():
        if key not in DOC_KEYS:
            raise HTTPException(status_code=400, detail=f"Unknown document type: {key}")
        if value is None:
            continue
        if not isinstance(value, dict):
            raise HTTPException(status_code=400, detail=f"{key} settings must be an object")
        merged = deepcopy(base[key])
        merged.update(value)
        base[key] = _normalize_series(merged, DEFAULTS[key])
    return base
