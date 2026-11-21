"""Gym equipment as assets: purchase details and straight-line depreciation.

Depreciation here is computed, not posted. The book value is cost less one equal share for every full
month since purchase, down to zero over the useful life. It is a report for the manager and the
accountant; nothing is journaled, so the ledger is never changed by a number that can be recomputed.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.gym import _audit, _money
from app.honesty import optional_honest_narrative


def months_between(start: date, end: date) -> int:
    n = (end.year - start.year) * 12 + (end.month - start.month)
    return max(0, n - (1 if end.day < start.day else 0))


def book_value(cost: float, life_months: int, bought: date, as_of: date) -> tuple[float, float]:
    """(accumulated depreciation, book value) as of a date."""
    used = min(months_between(bought, as_of), life_months)
    dep = round(cost * used / life_months, 2)
    return dep, round(cost - dep, 2)


async def set_asset(db: AsyncSession, tenant_id: str, equipment_id: str, payload, *, user_id) -> dict:
    row = await db.get(m.GymEquipment, equipment_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Equipment not found")
    if payload.purchase_date > date.today():
        raise HTTPException(status_code=422, detail="The purchase date cannot be in the future")
    if payload.warranty_until and payload.warranty_until < payload.purchase_date:
        raise HTTPException(status_code=422, detail="The warranty cannot end before the purchase")
    row.purchase_date, row.purchase_cost = payload.purchase_date, _money(payload.purchase_cost)
    row.useful_life_months, row.warranty_until = int(payload.useful_life_months), payload.warranty_until
    row.supplier_name = optional_honest_narrative(payload.supplier_name, label="supplier", max_length=150)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_equipment_asset_set", "gym_equipment", row.id, {"cost": _money(row.purchase_cost)})
    return present(row, date.today())


def present(row: m.GymEquipment, as_of: date) -> dict:
    out = {
        "id": row.id, "name": row.name, "category": row.category, "status": row.status,
        "purchase_date": row.purchase_date.isoformat() if row.purchase_date else None,
        "purchase_cost": _money(row.purchase_cost) if row.purchase_cost is not None else None,
        "useful_life_months": row.useful_life_months, "supplier_name": row.supplier_name,
        "warranty_until": row.warranty_until.isoformat() if row.warranty_until else None,
        "under_warranty": bool(row.warranty_until and row.warranty_until >= as_of),
        "accumulated_depreciation": None, "book_value": None,
    }
    if row.purchase_date and row.purchase_cost is not None and row.useful_life_months:
        dep, value = book_value(float(row.purchase_cost), int(row.useful_life_months), row.purchase_date, as_of)
        out["accumulated_depreciation"], out["book_value"] = dep, value
        out["fully_depreciated"] = value <= 0
    return out


async def asset_report(db: AsyncSession, tenant_id: str, *, as_of: date) -> dict:
    rows = (await db.execute(select(m.GymEquipment).where(m.GymEquipment.tenant_id == tenant_id).order_by(m.GymEquipment.name))).scalars().all()
    items = [present(r, as_of) for r in rows]
    priced = [i for i in items if i["book_value"] is not None and i["status"] != "retired"]
    return {
        "as_of": as_of.isoformat(), "items": items,
        "total_cost": round(sum(i["purchase_cost"] for i in priced), 2),
        "total_depreciation": round(sum(i["accumulated_depreciation"] for i in priced), 2),
        "total_book_value": round(sum(i["book_value"] for i in priced), 2),
        "note": "Straight-line, computed on the day you ask. Nothing is posted to the ledger. Retired equipment is left out of the totals.",
    }
