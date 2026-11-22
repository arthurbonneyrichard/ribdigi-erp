"""FMCG optional manufacturing routes. Managers and admins only; refused until the company switches it on."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_mfg as svc
from app import fmcg_orders as orders
from app.db import get_db
from app.schemas import PositiveMoneyValue, PositiveQtyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg/manufacturing", tags=["fmcg"])
Pay = Literal["cash", "card", "mobile_money", "bank_transfer", "cheque", "payable"]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class BomLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: UuidIdValue
    quantity: Annotated[float, Field(gt=0, le=1_000_000, allow_inf_nan=False)]
    wastage_pct: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] = 0


class BomBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    name: Annotated[str, Field(min_length=2, max_length=150)]
    output_qty: PositiveQtyValue = 1
    shelf_life_days: Annotated[int, Field(ge=1, le=3650)] | None = None
    lines: list[BomLine] = Field(max_length=100)


class BomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=2, max_length=150)]
    output_qty: PositiveQtyValue = 1
    shelf_life_days: Annotated[int, Field(ge=1, le=3650)] | None = None
    lines: list[BomLine] = Field(max_length=100)


class ActiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class SwitchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


class OrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bom_id: UuidIdValue
    planned_qty: PositiveQtyValue
    planned_date: date | None = None
    notes: Annotated[str, Field(min_length=3, max_length=500)] | None = None


class Used(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: UuidIdValue
    actual_qty: Annotated[float, Field(ge=0, le=1_000_000, allow_inf_nan=False)]


class Overhead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["labour", "power", "packaging", "transport", "other"]
    amount: PositiveMoneyValue
    pay_method: Pay
    note: Annotated[str, Field(min_length=3, max_length=300)] | None = None


class CompleteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    produced_qty: PositiveQtyValue
    batch_number: Annotated[str, Field(min_length=2, max_length=80)] | None = None
    expiry_date: date | None = None
    materials: list[Used] = Field(default_factory=list, max_length=100)
    overheads: list[Overhead] = Field(default_factory=list, max_length=20)
    hold_for_qc: bool = False


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=255)]


@router.get("/settings")
async def settings_get(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    return _env({"enabled": await svc.is_enabled(db, claims["tenant_id"])})


@router.put("/settings")
async def settings_put(payload: SwitchBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    data = await svc.set_enabled(db, claims["tenant_id"], payload.enabled, claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.get("/boms")
async def boms(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    return _env(await svc.list_boms(db, tenant_id=claims["tenant_id"]))


@router.post("/boms")
async def bom_create(payload: BomBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    data = await svc.create_bom(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), product_id=payload.product_id, name=payload.name,
        output_qty=float(payload.output_qty), shelf_life_days=payload.shelf_life_days, lines=[l.model_dump() for l in payload.lines],
    )
    await db.commit()
    return _env(data, "Recipe saved")


@router.put("/boms/{bom_id}")
async def bom_update(bom_id: UuidIdValue, payload: BomUpdate, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    data = await svc.update_bom(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), bom_id=bom_id, name=payload.name,
        output_qty=float(payload.output_qty), shelf_life_days=payload.shelf_life_days, lines=[l.model_dump() for l in payload.lines],
    )
    await db.commit()
    return _env(data, "Recipe saved")


@router.patch("/boms/{bom_id}")
async def bom_active(bom_id: UuidIdValue, payload: ActiveBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    data = await svc.set_bom_active(db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), bom_id=bom_id, active=payload.is_active)
    await db.commit()
    return _env(data, "Saved")


@router.get("/orders")
async def production_orders(
    status: Literal["planned", "in_progress", "completed", "cancelled"] | None = None,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "manufacturing")
    return _env(await svc.list_orders(db, tenant_id=claims["tenant_id"], status=status))


@router.post("/orders")
async def production_create(payload: OrderBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    data = await svc.create_order(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), bom_id=payload.bom_id, planned_qty=float(payload.planned_qty),
        planned_date=payload.planned_date, notes=payload.notes,
    )
    await db.commit()
    return _env(data, "Production planned")


@router.get("/orders/{order_id}")
async def production_get(order_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    await svc.require_enabled(db, claims["tenant_id"])
    return _env(await svc.detail(db, tenant_id=claims["tenant_id"], order_id=order_id))


@router.get("/orders/{order_id}/check")
async def production_check(order_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    return _env(await svc.check_materials(db, tenant_id=claims["tenant_id"], order_id=order_id))


@router.post("/orders/{order_id}/start")
async def production_start(order_id: UuidIdValue, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    data = await svc.start(db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), order_id=order_id)
    await db.commit()
    return _env(data, "Production started")


@router.post("/orders/{order_id}/complete")
async def production_complete(order_id: UuidIdValue, payload: CompleteBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    data = await svc.complete(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), order_id=order_id, produced_qty=float(payload.produced_qty),
        batch_number=payload.batch_number, expiry_date=payload.expiry_date,
        materials=[{"component_id": u.component_id, "actual_qty": u.actual_qty} for u in payload.materials],
        overheads=[{"kind": o.kind, "amount": float(o.amount), "pay_method": o.pay_method, "note": o.note} for o in payload.overheads],
        hold_for_qc=payload.hold_for_qc,
    )
    await db.commit()
    return _env(data, "Production completed")


@router.post("/orders/{order_id}/cancel")
async def production_cancel(order_id: UuidIdValue, payload: CancelBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "manufacturing")
    data = await svc.cancel(db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), order_id=order_id, reason=payload.reason)
    await db.commit()
    return _env(data, "Cancelled")


@router.get("/report")
async def production_report(
    start: date | None = None, end: date | None = None,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "manufacturing")
    stop = end or date.today()
    begin = start or stop - timedelta(days=29)
    if stop < begin or (stop - begin).days > 366:
        raise HTTPException(status_code=422, detail="Pick a period of 366 days or less, with the end after the start")
    return _env(await svc.report(db, tenant_id=claims["tenant_id"], start=begin, end=stop))
