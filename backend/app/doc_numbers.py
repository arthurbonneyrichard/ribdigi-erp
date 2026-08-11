"""Short daily document numbers: letter + YYMMDD + sequential 001."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

_SEQ_RE = re.compile(r"-(\d+)$")


def format_daily_number(prefix: str, day: str | None = None, seq: int = 1) -> str:
    """Build a short number like S260811-001."""
    day_part = day or datetime.utcnow().strftime("%y%m%d")
    return f"{prefix}{day_part}-{max(int(seq), 1):03d}"


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
    day = datetime.utcnow().strftime("%y%m%d")
    prefix = f"I{day}-"
    rows = (
        await db.execute(
            select(m.SalesInvoice.invoice_number).where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.invoice_number.like(f"{prefix}%"),
            )
        )
    ).scalars().all()
    return format_daily_number("I", day, _max_seq(list(rows), prefix) + 1)
