"""Customer groups + group-based pricing (BR-7.1)."""

from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, require_honest_narrative

DEFAULT_GROUPS = (
    ("RETAIL", "Retail", 0.0),
    ("WHOLESALE", "Wholesale", 10.0),
    ("VIP", "VIP", 15.0),
)


def _slug_code(name: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9]+", "_", (name or "").strip().upper()).strip("_")
    return (raw or "GROUP")[:40]


async def ensure_default_groups(db: AsyncSession, tenant_id: str) -> list[m.CustomerGroup]:
    existing = (
        await db.execute(
            select(m.CustomerGroup).where(m.CustomerGroup.tenant_id == tenant_id)
        )
    ).scalars().all()
    if existing:
        return list(existing)
    rows = []
    for code, name, pct in DEFAULT_GROUPS:
        row = m.CustomerGroup(
            tenant_id=tenant_id,
            code=code,
            name=name,
            discount_percent=pct,
            is_active=True,
        )
        db.add(row)
        rows.append(row)
    await db.flush()
    return rows


def serialize_group(row: m.CustomerGroup) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "discount_percent": money_json(row.discount_percent),
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


async def list_groups(
    db: AsyncSession, tenant_id: str, *, is_active: bool | None = None
) -> list[m.CustomerGroup]:
    await ensure_default_groups(db, tenant_id)
    stmt = (
        select(m.CustomerGroup)
        .where(m.CustomerGroup.tenant_id == tenant_id)
        .order_by(m.CustomerGroup.name.asc())
    )
    if is_active is not None:
        stmt = stmt.where(m.CustomerGroup.is_active.is_(bool(is_active)))
    return list((await db.execute(stmt)).scalars().all())


async def get_group(db: AsyncSession, tenant_id: str, group_id: str) -> m.CustomerGroup:
    row = (
        await db.execute(
            select(m.CustomerGroup).where(
                m.CustomerGroup.id == group_id,
                m.CustomerGroup.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Customer group not found")
    return row


async def require_active_group(
    db: AsyncSession, tenant_id: str, group_id: str
) -> m.CustomerGroup:
    """Resolve a group for assignment; inactive groups cannot be newly assigned."""
    row = await get_group(db, tenant_id, group_id)
    if not row.is_active:
        raise HTTPException(status_code=400, detail="Customer group is inactive")
    return row


async def create_group(
    db: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    code: str | None = None,
    discount_percent: float = 0,
) -> m.CustomerGroup:
    await ensure_default_groups(db, tenant_id)
    name = require_honest_narrative(name, label="customer group name", max_length=120)
    # OpenAPI CustomerGroupCodeValue → 422; service defense-in-depth → 400.
    if code is not None and str(code).strip():
        code_key = require_honest_narrative(
            str(code).strip().upper(), label="customer group code", max_length=40
        )
    else:
        code_key = _slug_code(name).strip().upper()[:40]
    pct = money_json(discount_percent or 0)
    if pct < 0 or pct > 100:
        raise HTTPException(status_code=422, detail="discount_percent must be between 0 and 100")
    exists = (
        await db.execute(
            select(m.CustomerGroup).where(
                m.CustomerGroup.tenant_id == tenant_id,
                m.CustomerGroup.code == code_key,
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Customer group code already exists")
    row = m.CustomerGroup(
        tenant_id=tenant_id,
        code=code_key,
        name=name,
        discount_percent=pct,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def update_group(
    db: AsyncSession,
    *,
    tenant_id: str,
    group_id: str,
    name: str | None = None,
    discount_percent: float | None = None,
    is_active: bool | None = None,
) -> m.CustomerGroup:
    row = await get_group(db, tenant_id, group_id)
    if name is not None:
        row.name = require_honest_narrative(
            name, label="customer group name", max_length=120
        )
    if discount_percent is not None:
        pct = money_json(discount_percent)
        if pct < 0 or pct > 100:
            raise HTTPException(status_code=422, detail="discount_percent must be between 0 and 100")
        row.discount_percent = pct
    if is_active is not None:
        row.is_active = bool(is_active)
    await db.flush()
    return row


async def customer_group_discount(
    db: AsyncSession, tenant_id: str, customer_id: str | None
) -> tuple[float, m.CustomerGroup | None]:
    """Return (discount_percent, group) for a customer, or (0, None)."""
    if not customer_id:
        return 0.0, None
    party = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == customer_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "customer",
            )
        )
    ).scalar_one_or_none()
    if not party or not getattr(party, "customer_group_id", None):
        return 0.0, None
    group = (
        await db.execute(
            select(m.CustomerGroup).where(
                m.CustomerGroup.id == party.customer_group_id,
                m.CustomerGroup.tenant_id == tenant_id,
                m.CustomerGroup.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not group:
        return 0.0, None
    return money_json(group.discount_percent or 0), group


def apply_discount(base_price: float, discount_percent: float) -> float:
    base = money_json(base_price or 0)
    pct = max(0.0, min(100.0, money_json(discount_percent or 0)))
    return money_json(round(base * (1.0 - pct / 100.0), 2))
