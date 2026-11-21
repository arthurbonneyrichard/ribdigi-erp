"""FMCG warehouse layout routes: zones, bins, put-away, moves, counts, scan, pick lists. Managers and admins."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_orders as orders
from app import fmcg_warehouse as svc
from app.db import get_db
from app.schemas import NonNegativeQtyValue, PositiveQtyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg", tags=["fmcg"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class LocationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warehouse_id: UuidIdValue
    kind: Literal["zone", "bin"]
    code: Annotated[str, Field(min_length=1, max_length=30)]
    name: Annotated[str, Field(min_length=2, max_length=120)]
    parent_id: UuidIdValue | None = None
    zone_type: Literal["ambient", "cold", "bulk", "quarantine", "receiving", "dispatch", "returns"] | None = None
    capacity: PositiveQtyValue | None = None
    pick_order: Annotated[int, Field(ge=1, le=10000)] = 100


class ActiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class PutAwayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bin_id: UuidIdValue
    product_id: UuidIdValue
    batch_id: UuidIdValue | None = None
    quantity: PositiveQtyValue


class MoveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_bin_id: UuidIdValue
    to_bin_id: UuidIdValue
    product_id: UuidIdValue
    batch_id: UuidIdValue | None = None
    quantity: PositiveQtyValue


class CountLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    batch_id: UuidIdValue | None = None
    counted: NonNegativeQtyValue


class CountBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[CountLine] = Field(max_length=500)
    note: Annotated[str, Field(min_length=3, max_length=500)] | None = None


@router.get("/locations")
async def location_tree(
    warehouse_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "warehouse")
    return _env(await svc.list_tree(db, tenant_id=claims["tenant_id"], warehouse_id=warehouse_id))


@router.post("/locations")
async def location_create(
    payload: LocationBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "warehouse")
    data = await svc.create_location(
        db, tenant_id=claims["tenant_id"], warehouse_id=payload.warehouse_id, kind=payload.kind, code=payload.code,
        name=payload.name, parent_id=payload.parent_id, zone_type=payload.zone_type,
        capacity=float(payload.capacity) if payload.capacity is not None else None,
        pick_order=payload.pick_order, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Saved")


@router.patch("/locations/{location_id}")
async def location_active(
    location_id: UuidIdValue, payload: ActiveBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "warehouse")
    data = await svc.set_active(
        db, tenant_id=claims["tenant_id"], location_id=location_id, is_active=payload.is_active, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Saved")


@router.get("/locations/scan")
async def location_scan(
    code: Annotated[str, Query(min_length=1, max_length=30)],
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "warehouse")
    return _env(await svc.scan(db, tenant_id=claims["tenant_id"], code=code))


@router.get("/locations/{bin_id}/contents")
async def location_contents(
    bin_id: UuidIdValue, blind: bool = False,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "warehouse")
    return _env(await svc.contents(db, tenant_id=claims["tenant_id"], bin_id=bin_id, blind=blind))


@router.post("/locations/{bin_id}/count")
async def location_count(
    bin_id: UuidIdValue, payload: CountBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "warehouse")
    data = await svc.count_bin(
        db, tenant_id=claims["tenant_id"], bin_id=bin_id,
        lines=[{"product_id": l.product_id, "batch_id": l.batch_id, "counted": l.counted} for l in payload.lines],
        note=payload.note, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Count saved")


@router.post("/warehouse/put-away")
async def warehouse_put_away(
    payload: PutAwayBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "warehouse")
    data = await svc.put_away(
        db, tenant_id=claims["tenant_id"], bin_id=payload.bin_id, product_id=payload.product_id,
        batch_id=payload.batch_id, quantity=payload.quantity, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Put away")


@router.post("/warehouse/move")
async def warehouse_move(
    payload: MoveBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "warehouse")
    data = await svc.move(
        db, tenant_id=claims["tenant_id"], from_bin=payload.from_bin_id, to_bin=payload.to_bin_id,
        product_id=payload.product_id, batch_id=payload.batch_id, quantity=payload.quantity, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Moved")


@router.get("/warehouse/suggest")
async def warehouse_suggest(
    product_id: UuidIdValue, quantity: Annotated[float, Query(gt=0, le=1_000_000)], batch_id: UuidIdValue | None = None,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "warehouse")
    return _env(await svc.suggest_bins(db, tenant_id=claims["tenant_id"], product_id=product_id, batch_id=batch_id, quantity=quantity))


@router.get("/warehouse/report")
async def warehouse_report(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "warehouse")
    return _env(await svc.report(db, tenant_id=claims["tenant_id"]))


@router.get("/orders/{order_id}/pick-list")
async def order_pick_list(
    order_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "warehouse")
    return _env(await svc.pick_list(db, tenant_id=claims["tenant_id"], order_id=order_id))
