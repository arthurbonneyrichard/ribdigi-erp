"""FMCG merchandising routes. Reps and drivers can audit and note prices; managers set the list and read reports."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_merch as svc
from app import fmcg_orders as orders
from app.db import get_db
from app.schemas import PositiveMoneyValue, NonNegativeMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg/merch", tags=["fmcg"])
MANAGERS = frozenset({"company_admin", "fmcg_manager", "super_admin"})
Image = Annotated[str, Field(max_length=1_200_000)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def _is_manager(claims) -> bool:
    return str(claims.get("role") or "") in MANAGERS


class MustItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    min_facings: Annotated[int, Field(ge=1, le=50)] = 1


class MustBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MustItem] = Field(max_length=200)


class AuditLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    present: bool
    facings: Annotated[int, Field(ge=0, le=500)] = 0
    shelf_price: NonNegativeMoneyValue | None = None


class AuditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outlet_id: UuidIdValue
    visit_id: UuidIdValue | None = None
    display_ok: bool | None = None
    notes: Annotated[str, Field(min_length=3, max_length=500)] | None = None
    photo: Image | None = None
    lines: list[AuditLine] = Field(max_length=300)


class PriceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outlet_id: UuidIdValue | None = None
    product_id: UuidIdValue
    competitor_brand: Annotated[str, Field(min_length=2, max_length=120)]
    competitor_product: Annotated[str, Field(min_length=2, max_length=160)]
    price: PositiveMoneyValue
    note: Annotated[str, Field(min_length=3, max_length=300)] | None = None


@router.get("/must-stock")
async def must_get(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "merch")
    return _env(await svc.get_must_stock(db, tenant_id=claims["tenant_id"]))


@router.put("/must-stock")
async def must_put(payload: MustBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "merch")
    if not _is_manager(claims):
        raise HTTPException(status_code=403, detail={"code": "FMCG_ROLE_JOB", "message": "A manager sets the must-stock list."})
    data = await svc.set_must_stock(
        db, tenant_id=claims["tenant_id"], items=[{"product_id": i.product_id, "min_facings": i.min_facings} for i in payload.items], user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Saved")


@router.post("/audits")
async def audit_create(payload: AuditBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "merch")
    data = await svc.create_audit(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), may_audit_any=_is_manager(claims), outlet_id=payload.outlet_id,
        visit_id=payload.visit_id, display_ok=payload.display_ok, notes=payload.notes, photo=payload.photo,
        lines=[{"product_id": l.product_id, "present": l.present, "facings": l.facings, "shelf_price": float(l.shelf_price) if l.shelf_price is not None else None} for l in payload.lines],
    )
    await db.commit()
    return _env(data, "Shelf audit saved")


@router.get("/audits")
async def audit_list(
    outlet_id: UuidIdValue | None = None, days: Annotated[int, Query(ge=1, le=365)] = 30,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "merch")
    return _env(await svc.list_audits(
        db, tenant_id=claims["tenant_id"], user_id=None if _is_manager(claims) else claims.get("sub"), outlet_id=outlet_id, days=days))


@router.get("/audits/{audit_id}")
async def audit_get(audit_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "merch")
    return _env(await svc.get_audit(db, tenant_id=claims["tenant_id"], audit_id=audit_id, user_id=None if _is_manager(claims) else claims.get("sub")))


@router.post("/competitor-prices")
async def price_add(payload: PriceBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "merch")
    data = await svc.add_competitor_price(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), outlet_id=payload.outlet_id, product_id=payload.product_id,
        brand=payload.competitor_brand, competitor_product=payload.competitor_product, price=float(payload.price), note=payload.note,
    )
    await db.commit()
    return _env(data, "Price noted")


@router.get("/competitor-prices")
async def price_list(
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "merch")
    if not _is_manager(claims):
        raise HTTPException(status_code=403, detail={"code": "FMCG_ROLE_JOB", "message": "Managers read the price list."})
    return _env(await svc.list_competitor_prices(db, tenant_id=claims["tenant_id"], days=days))


@router.get("/report")
async def merch_report(
    start: date | None = None, end: date | None = None,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "merch")
    if not _is_manager(claims):
        raise HTTPException(status_code=403, detail={"code": "FMCG_ROLE_JOB", "message": "Managers read the shelf report."})
    stop = end or date.today()
    begin = start or stop - timedelta(days=29)
    if stop < begin or (stop - begin).days > 366:
        raise HTTPException(status_code=422, detail="Pick a period of 366 days or less, with the end after the start")
    return _env(await svc.report(db, tenant_id=claims["tenant_id"], start=begin, end=stop))
