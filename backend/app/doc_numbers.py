"""Document number helpers: daily sequences and configurable sales invoice series."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

_SEQ_RE = re.compile(r"-(\d+)$")
_PREFIX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$")
DEFAULT_INVOICE_PREFIX = "INV"
INVOICE_SERIES_PAD = 4


def format_daily_number(prefix: str, day: str | None = None, seq: int = 1) -> str:
    """Build a short number like S260811-001."""
    day_part = day or datetime.utcnow().strftime("%y%m%d")
    return f"{prefix}{day_part}-{max(int(seq), 1):03d}"


def format_series_number(prefix: str, year: int, seq: int, *, pad: int = INVOICE_SERIES_PAD) -> str:
    """Build INV-2026-0001 style series numbers."""
    return f"{prefix}-{int(year)}-{max(int(seq), 1):0{int(pad)}d}"


def normalize_invoice_prefix(prefix: str | None) -> str:
    text = (prefix or DEFAULT_INVOICE_PREFIX).strip().upper()
    if not text or not _PREFIX_RE.match(text):
        raise HTTPException(
            status_code=400,
            detail="Invoice prefix must be 1–20 chars: letters, digits, underscore, or hyphen",
        )
    return text


def invoice_numbering_settings(tenant: m.Tenant, *, as_of: datetime | None = None) -> dict:
    """Serialize tenant invoice numbering config + next preview (no side effects)."""
    now = as_of or datetime.utcnow()
    year = now.year
    prefix = normalize_invoice_prefix(getattr(tenant, "sales_invoice_number_prefix", None))
    stored_year = getattr(tenant, "sales_invoice_number_year", None)
    next_seq = int(getattr(tenant, "sales_invoice_number_next", None) or 1)
    if stored_year is not None and int(stored_year) != year:
        next_seq = 1
    return {
        "prefix": prefix,
        "next_number": max(next_seq, 1),
        "year": year,
        "pad": INVOICE_SERIES_PAD,
        "pattern": f"{prefix}-{{YYYY}}-{{NNNN}}",
        "preview": format_series_number(prefix, year, max(next_seq, 1)),
    }


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


async def next_sales_invoice_number(db: AsyncSession, tenant_id: str) -> str:
    """Allocate next `{prefix}-{YYYY}-{NNNN}` for the tenant (year-scoped series)."""
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id).with_for_update())
    ).scalar_one()
    year = datetime.utcnow().year
    prefix = normalize_invoice_prefix(getattr(tenant, "sales_invoice_number_prefix", None))
    stored_year = getattr(tenant, "sales_invoice_number_year", None)
    if stored_year is None or int(stored_year) != year:
        tenant.sales_invoice_number_year = year
        tenant.sales_invoice_number_next = 1

    # Skip collisions (legacy Iyyymmdd numbers or admin-advanced series)
    for _ in range(10_000):
        seq = max(int(tenant.sales_invoice_number_next or 1), 1)
        candidate = format_series_number(prefix, year, seq)
        tenant.sales_invoice_number_next = seq + 1
        exists = (
            await db.execute(
                select(m.SalesInvoice.id).where(
                    m.SalesInvoice.tenant_id == tenant_id,
                    m.SalesInvoice.invoice_number == candidate,
                )
            )
        ).scalar_one_or_none()
        if not exists:
            await db.flush()
            return candidate

    raise HTTPException(status_code=500, detail="Unable to allocate sales invoice number")


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
