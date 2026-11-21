"""FMCG fleet routes. Managers and admins only."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_fleet as svc
from app import fmcg_orders as orders
from app.db import get_db
from app.schemas import NonNegativeMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg", tags=["fmcg"])

Km = Annotated[float, Field(ge=0, le=5_000_000, allow_inf_nan=False)]
Method = Literal["cash", "card", "mobile_money", "bank_transfer", "cheque"]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class VehicleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plate: Annotated[str, Field(min_length=2, max_length=20)]
    name: Annotated[str, Field(min_length=2, max_length=120)]
    kind: Literal["van", "truck", "pickup", "motorbike", "other"] = "van"
    make_model: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    driver_user_id: UuidIdValue | None = None
    odometer_km: Km = 0
    insurance_expiry: date | None = None
    roadworthy_expiry: date | None = None
    licence_expiry: date | None = None
    service_every_km: Annotated[float, Field(gt=0, le=1_000_000, allow_inf_nan=False)] | None = None
    last_service_km: Km | None = None


class VehicleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    status: Literal["active", "workshop", "retired"] | None = None
    driver_user_id: UuidIdValue | None = None
    insurance_expiry: date | None = None
    roadworthy_expiry: date | None = None
    licence_expiry: date | None = None
    service_every_km: Annotated[float, Field(gt=0, le=1_000_000, allow_inf_nan=False)] | None = None


class LogBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["fuel", "service", "repair", "tyre", "accident", "other"]
    log_date: date | None = None
    odometer_km: Km | None = None
    litres: Annotated[float, Field(gt=0, le=100000, allow_inf_nan=False)] | None = None
    amount: NonNegativeMoneyValue = 0
    vendor: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    note: Annotated[str, Field(min_length=3, max_length=500)] | None = None
    pay_method: Method | None = None


class AssignBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_id: UuidIdValue


@router.get("/fleet/vehicles")
async def fleet_list(
    status: Literal["active", "workshop", "retired"] | None = None,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "fleet")
    return _env(await svc.list_vehicles(db, tenant_id=claims["tenant_id"], status=status))


@router.post("/fleet/vehicles")
async def fleet_add(
    payload: VehicleBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "fleet")
    data = await svc.create_vehicle(
        db, tenant_id=claims["tenant_id"], plate=payload.plate, name=payload.name, kind=payload.kind,
        make_model=payload.make_model, driver_user_id=payload.driver_user_id, odometer_km=payload.odometer_km,
        insurance_expiry=payload.insurance_expiry, roadworthy_expiry=payload.roadworthy_expiry,
        licence_expiry=payload.licence_expiry, service_every_km=payload.service_every_km,
        last_service_km=payload.last_service_km, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Vehicle added")


@router.patch("/fleet/vehicles/{vehicle_id}")
async def fleet_update(
    vehicle_id: UuidIdValue, payload: VehicleUpdate,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "fleet")
    data = await svc.update_vehicle(
        db, tenant_id=claims["tenant_id"], vehicle_id=vehicle_id,
        changes=payload.model_dump(exclude_unset=True), user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Saved")


@router.get("/fleet/vehicles/{vehicle_id}/logs")
async def fleet_logs(
    vehicle_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "fleet")
    return _env(await svc.list_logs(db, tenant_id=claims["tenant_id"], vehicle_id=vehicle_id))


@router.post("/fleet/vehicles/{vehicle_id}/logs")
async def fleet_add_log(
    vehicle_id: UuidIdValue, payload: LogBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "fleet")
    data = await svc.add_log(
        db, tenant_id=claims["tenant_id"], vehicle_id=vehicle_id, kind=payload.kind, log_date=payload.log_date,
        odometer_km=payload.odometer_km, litres=payload.litres, amount=float(payload.amount or 0), vendor=payload.vendor,
        note=payload.note, pay_method=payload.pay_method, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Recorded")


@router.get("/fleet/attention")
async def fleet_attention(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "fleet")
    return _env(await svc.attention(db, tenant_id=claims["tenant_id"]))


@router.get("/fleet/report")
async def fleet_report(
    start: date, end: date, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "fleet")
    if end < start:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="The end date is before the start date")
    return _env(await svc.cost_report(db, tenant_id=claims["tenant_id"], start=start, end=end))


@router.post("/dispatches/{dispatch_id}/vehicle")
async def dispatch_vehicle(
    dispatch_id: UuidIdValue, payload: AssignBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "dispatch_vehicle")
    data = await svc.assign_to_dispatch(
        db, tenant_id=claims["tenant_id"], dispatch_id=dispatch_id, vehicle_id=payload.vehicle_id, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Vehicle assigned")
