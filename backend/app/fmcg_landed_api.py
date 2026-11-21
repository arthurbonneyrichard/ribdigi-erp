"""FMCG import shipment and landed cost routes. Managers and admins only."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_landed as svc
from app import fmcg_orders as orders
from app.db import get_db
from app.schemas import NonNegativeMoneyValue, PositiveMoneyValue, PositiveQtyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg/shipments", tags=["fmcg"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class ShipmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference: Annotated[str, Field(min_length=2, max_length=80)] | None = None
    container_no: Annotated[str, Field(min_length=2, max_length=40)] | None = None
    supplier_id: UuidIdValue | None = None
    grn_id: UuidIdValue | None = None
    eta: date | None = None
    basis: Literal["value", "quantity"] = "value"
    notes: Annotated[str, Field(min_length=3, max_length=500)] | None = None


class LineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: PositiveQtyValue
    goods_value: NonNegativeMoneyValue


class CostBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["freight", "insurance", "customs_duty", "port", "clearing", "transport", "other"]
    amount: PositiveMoneyValue
    vendor: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    pay_method: Literal["cash", "card", "mobile_money", "bank_transfer", "cheque", "payable"]
    note: Annotated[str, Field(min_length=3, max_length=300)] | None = None


@router.get("")
async def shipments(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "imports")
    return _env(await svc.list_all(db, tenant_id=claims["tenant_id"]))


@router.post("")
async def shipment_create(payload: ShipmentBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "imports")
    data = await svc.create(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), reference=payload.reference, container_no=payload.container_no,
        supplier_id=payload.supplier_id, grn_id=payload.grn_id, eta=payload.eta, basis=payload.basis, notes=payload.notes,
    )
    await db.commit()
    return _env(data, "Shipment opened")


@router.get("/{shipment_id}")
async def shipment_get(shipment_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "imports")
    return _env(await svc.detail(db, tenant_id=claims["tenant_id"], shipment_id=shipment_id))


@router.post("/{shipment_id}/lines")
async def shipment_line(shipment_id: UuidIdValue, payload: LineBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "imports")
    data = await svc.add_line(
        db, tenant_id=claims["tenant_id"], shipment_id=shipment_id, product_id=payload.product_id,
        quantity=float(payload.quantity), goods_value=float(payload.goods_value), user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Added")


@router.delete("/{shipment_id}/lines/{line_id}")
async def shipment_line_delete(shipment_id: UuidIdValue, line_id: UuidIdValue, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "imports")
    data = await svc.remove_line(db, tenant_id=claims["tenant_id"], shipment_id=shipment_id, line_id=line_id)
    await db.commit()
    return _env(data, "Removed")


@router.post("/{shipment_id}/costs")
async def shipment_cost(shipment_id: UuidIdValue, payload: CostBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "imports")
    data = await svc.add_cost(
        db, tenant_id=claims["tenant_id"], shipment_id=shipment_id, kind=payload.kind, amount=float(payload.amount),
        vendor=payload.vendor, pay_method=payload.pay_method, note=payload.note, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Added")


@router.delete("/{shipment_id}/costs/{cost_id}")
async def shipment_cost_delete(shipment_id: UuidIdValue, cost_id: UuidIdValue, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "imports")
    data = await svc.remove_cost(db, tenant_id=claims["tenant_id"], shipment_id=shipment_id, cost_id=cost_id)
    await db.commit()
    return _env(data, "Removed")


@router.post("/{shipment_id}/allocate")
async def shipment_allocate(shipment_id: UuidIdValue, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "imports")
    data = await svc.allocate(db, tenant_id=claims["tenant_id"], shipment_id=shipment_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Costs added to the goods")


@router.post("/{shipment_id}/cancel")
async def shipment_cancel(shipment_id: UuidIdValue, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "imports")
    data = await svc.cancel(db, tenant_id=claims["tenant_id"], shipment_id=shipment_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Cancelled")
