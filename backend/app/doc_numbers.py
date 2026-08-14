"""Document number helpers: daily sequences and configurable year series."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

_SEQ_RE = re.compile(r"-(\d+)$")
_PREFIX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$")
SERIES_PAD = 4

# kind -> default prefix + uniqueness model/column (JSON kinds use document_numbering)
SERIES_KINDS: dict[str, dict[str, Any]] = {
    "sales_invoice": {
        "default_prefix": "INV",
        "storage": "columns",
        "model": m.SalesInvoice,
        "field": "invoice_number",
    },
    "quotation": {
        "default_prefix": "QT",
        "storage": "json",
        "model": m.SalesQuotation,
        "field": "quotation_number",
    },
    "purchase_order": {
        "default_prefix": "PO",
        "storage": "json",
        "model": m.PurchaseOrder,
        "field": "po_number",
    },
    "grn": {
        "default_prefix": "GRN",
        "storage": "json",
        "model": m.GoodsReceipt,
        "field": "grn_number",
    },
    "purchase_invoice": {
        "default_prefix": "PINV",
        "storage": "json",
        "model": m.PurchaseInvoice,
        "field": "invoice_number",
    },
}

# Back-compat aliases
DEFAULT_INVOICE_PREFIX = SERIES_KINDS["sales_invoice"]["default_prefix"]
INVOICE_SERIES_PAD = SERIES_PAD


def format_daily_number(prefix: str, day: str | None = None, seq: int = 1) -> str:
    """Build a short number like S260811-001."""
    day_part = day or datetime.utcnow().strftime("%y%m%d")
    return f"{prefix}{day_part}-{max(int(seq), 1):03d}"


def format_series_number(prefix: str, year: int, seq: int, *, pad: int = SERIES_PAD) -> str:
    """Build INV-2026-0001 style series numbers."""
    return f"{prefix}-{int(year)}-{max(int(seq), 1):0{int(pad)}d}"


def normalize_prefix(prefix: str | None, *, default: str = "INV") -> str:
    text = (prefix or default).strip().upper()
    if not text or not _PREFIX_RE.match(text):
        raise HTTPException(
            status_code=400,
            detail="Document prefix must be 1–20 chars: letters, digits, underscore, or hyphen",
        )
    return text


def normalize_invoice_prefix(prefix: str | None) -> str:
    return normalize_prefix(prefix, default=DEFAULT_INVOICE_PREFIX)


def _json_bucket(tenant: m.Tenant) -> dict:
    raw = getattr(tenant, "document_numbering", None) or {}
    return dict(raw) if isinstance(raw, dict) else {}


def _read_state(tenant: m.Tenant, kind: str) -> tuple[str, int, int | None]:
    meta = SERIES_KINDS[kind]
    default_prefix = meta["default_prefix"]
    if meta["storage"] == "columns":
        prefix = getattr(tenant, "sales_invoice_number_prefix", None) or default_prefix
        next_seq = int(getattr(tenant, "sales_invoice_number_next", None) or 1)
        year = getattr(tenant, "sales_invoice_number_year", None)
        return prefix, next_seq, year
    bucket = _json_bucket(tenant).get(kind) or {}
    prefix = bucket.get("prefix") or default_prefix
    next_seq = int(bucket.get("next") or 1)
    year = bucket.get("year")
    return prefix, next_seq, int(year) if year is not None else None


def _write_state(tenant: m.Tenant, kind: str, *, prefix: str, next_seq: int, year: int) -> None:
    meta = SERIES_KINDS[kind]
    if meta["storage"] == "columns":
        tenant.sales_invoice_number_prefix = prefix
        tenant.sales_invoice_number_next = next_seq
        tenant.sales_invoice_number_year = year
        return
    data = _json_bucket(tenant)
    data[kind] = {"prefix": prefix, "next": next_seq, "year": year}
    tenant.document_numbering = data


def numbering_settings(tenant: m.Tenant, kind: str, *, as_of: datetime | None = None) -> dict:
    """Serialize numbering config + next preview for one document kind (no side effects)."""
    if kind not in SERIES_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown numbering kind: {kind}")
    now = as_of or datetime.utcnow()
    year = now.year
    raw_prefix, next_seq, stored_year = _read_state(tenant, kind)
    prefix = normalize_prefix(raw_prefix, default=SERIES_KINDS[kind]["default_prefix"])
    if stored_year is not None and int(stored_year) != year:
        next_seq = 1
    next_seq = max(int(next_seq), 1)
    return {
        "kind": kind,
        "prefix": prefix,
        "next_number": next_seq,
        "year": year,
        "pad": SERIES_PAD,
        "pattern": f"{prefix}-{{YYYY}}-{{NNNN}}",
        "preview": format_series_number(prefix, year, next_seq),
    }


def invoice_numbering_settings(tenant: m.Tenant, *, as_of: datetime | None = None) -> dict:
    return numbering_settings(tenant, "sales_invoice", as_of=as_of)


def all_numbering_settings(tenant: m.Tenant, *, as_of: datetime | None = None) -> dict:
    return {kind: numbering_settings(tenant, kind, as_of=as_of) for kind in SERIES_KINDS}


def apply_numbering_update(
    tenant: m.Tenant,
    kind: str,
    *,
    prefix: str,
    next_number: int,
    as_of: datetime | None = None,
) -> dict:
    if kind not in SERIES_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown numbering kind: {kind}")
    year = (as_of or datetime.utcnow()).year
    clean = normalize_prefix(prefix, default=SERIES_KINDS[kind]["default_prefix"])
    _write_state(tenant, kind, prefix=clean, next_seq=max(int(next_number), 1), year=year)
    return numbering_settings(tenant, kind, as_of=as_of)


def _max_seq(references: list[str], prefix: str) -> int:
    seq = 0
    for ref in references:
        text = str(ref or "")
        if not text.startswith(prefix):
            continue
        match = _SEQ_RE.search(text)
        if not match:
            continue
        try:
            seq = max(seq, int(match.group(1)))
        except ValueError:
            continue
    return seq


async def next_daily_number(
    db: AsyncSession,
    *,
    tenant_id: str,
    prefix: str,
    references: list[str],
) -> str:
    day = datetime.utcnow().strftime("%y%m%d")
    full_prefix = f"{prefix}{day}-"
    seq = _max_seq(references, full_prefix) + 1
    return format_daily_number(prefix, day, seq)


async def next_pos_sale_number(db: AsyncSession, tenant_id: str) -> str:
    day = datetime.utcnow().strftime("%y%m%d")
    prefix = f"S{day}-"
    rows = (
        await db.execute(
            select(m.Transaction.reference).where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
                m.Transaction.reference.like(f"{prefix}%"),
            )
        )
    ).scalars().all()
    return format_daily_number("S", day, _max_seq(list(rows), prefix) + 1)


async def next_series_document_number(db: AsyncSession, tenant_id: str, kind: str) -> str:
    """Allocate next `{prefix}-{YYYY}-{NNNN}` for the given document kind."""
    if kind not in SERIES_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown numbering kind: {kind}")
    meta = SERIES_KINDS[kind]
    model = meta["model"]
    field_name = meta["field"]
    number_col = getattr(model, field_name)

    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id).with_for_update())
    ).scalar_one()
    year = datetime.utcnow().year
    raw_prefix, next_seq, stored_year = _read_state(tenant, kind)
    prefix = normalize_prefix(raw_prefix, default=meta["default_prefix"])
    if stored_year is None or int(stored_year) != year:
        next_seq = 1
        stored_year = year

    for _ in range(10_000):
        seq = max(int(next_seq), 1)
        candidate = format_series_number(prefix, year, seq)
        next_seq = seq + 1
        _write_state(tenant, kind, prefix=prefix, next_seq=next_seq, year=year)
        exists = (
            await db.execute(
                select(model.id).where(
                    model.tenant_id == tenant_id,
                    number_col == candidate,
                )
            )
        ).scalar_one_or_none()
        if not exists:
            await db.flush()
            return candidate

    raise HTTPException(status_code=500, detail=f"Unable to allocate {kind} number")


async def next_sales_invoice_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "sales_invoice")


async def next_quotation_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "quotation")


async def next_purchase_order_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "purchase_order")


async def next_grn_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "grn")


async def next_purchase_invoice_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_series_document_number(db, tenant_id, "purchase_invoice")


async def next_purchase_request_number(db: AsyncSession, tenant_id: str) -> str:
    day = datetime.utcnow().strftime("%y%m%d")
    prefix = f"R{day}-"
    rows = (
        await db.execute(
            select(m.PurchaseRequest.request_number).where(
                m.PurchaseRequest.tenant_id == tenant_id,
                m.PurchaseRequest.request_number.like(f"{prefix}%"),
            )
        )
    ).scalars().all()
    return format_daily_number("R", day, _max_seq(list(rows), prefix) + 1)
