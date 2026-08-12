"""CSV export for customers and suppliers (Stage 119 E1)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

CUSTOMER_EXPORT_COLUMNS = [
    "name",
    "code",
    "party_type",
    "status",
    "email",
    "phone",
    "address",
    "payment_terms_days",
    "credit_limit",
    "balance",
    "notes",
]

SUPPLIER_EXPORT_COLUMNS = [
    "name",
    "code",
    "party_type",
    "category",
    "status",
    "email",
    "phone",
    "address",
    "payment_terms_days",
    "early_pay_discount_pct",
    "early_pay_discount_days",
    "credit_limit",
    "balance",
    "notes",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))
    return str(value)


async def export_customers_csv(db: AsyncSession, *, tenant_id: str) -> str:
    """Stage 119 E1 — export tenant customers as CSV."""
    rows = (
        await db.execute(
            select(m.Party)
            .where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer")
            .order_by(m.Party.name)
        )
    ).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CUSTOMER_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "name": _cell(row.name),
                "code": _cell(row.code),
                "party_type": _cell(row.party_type or "registered"),
                "status": _cell(row.status or "active"),
                "email": _cell(row.email),
                "phone": _cell(row.phone),
                "address": _cell(row.address),
                "payment_terms_days": _cell(int(row.payment_terms_days or 0)),
                "credit_limit": _cell(float(row.credit_limit or 0)),
                "balance": _cell(float(row.balance or 0)),
                "notes": _cell(row.notes),
            }
        )
    return buf.getvalue()


async def export_suppliers_csv(db: AsyncSession, *, tenant_id: str) -> str:
    """Stage 119 E1 — export tenant suppliers as CSV."""
    rows = (
        await db.execute(
            select(m.Party)
            .where(m.Party.tenant_id == tenant_id, m.Party.kind == "supplier")
            .order_by(m.Party.name)
        )
    ).scalars().all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SUPPLIER_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        pct = getattr(row, "early_pay_discount_pct", None)
        days = getattr(row, "early_pay_discount_days", None)
        writer.writerow(
            {
                "name": _cell(row.name),
                "code": _cell(row.code),
                "party_type": _cell(row.party_type),
                "category": _cell(row.category),
                "status": _cell(row.status or "active"),
                "email": _cell(row.email),
                "phone": _cell(row.phone),
                "address": _cell(row.address),
                "payment_terms_days": _cell(int(row.payment_terms_days or 0)),
                "early_pay_discount_pct": "" if pct is None else _cell(float(pct)),
                "early_pay_discount_days": "" if days is None else _cell(int(days)),
                "credit_limit": _cell(float(row.credit_limit or 0)),
                "balance": _cell(float(row.balance or 0)),
                "notes": _cell(row.notes),
            }
        )
    return buf.getvalue()
