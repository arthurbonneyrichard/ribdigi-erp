"""FMCG van sales routes. Rep, driver, manager and admin may run a van; closing with a difference needs a manager."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_orders as orders
from app import fmcg_van as svc
from app import models as m
from app import receipt_print
from app.db import get_db
from app.fmcg_orders_api import Method, OrderBody, OVERRIDE_ROLES
from app.schemas import NonNegativeMoneyValue, PositiveMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg", tags=["fmcg"])

Qty = Annotated[float, Field(gt=0, le=1000000, allow_inf_nan=False)]
Count = Annotated[float, Field(ge=0, le=1000000, allow_inf_nan=False)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class LoadLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty


class LoadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[LoadLine] = Field(min_length=1, max_length=200)


class VanSaleBody(OrderBody):
    payment_method: Method | None = None


class LossBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty
    kind: Literal["damaged", "sample"]
    note: Annotated[str, Field(min_length=3, max_length=255)]


class ExpenseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["fuel", "toll", "parking", "meal", "other"]
    amount: PositiveMoneyValue
    note: Annotated[str, Field(min_length=3, max_length=255)] | None = None


class CountLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Count


class CloseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted: list[CountLine] = Field(max_length=200)
    counted_cash: NonNegativeMoneyValue
    note: Annotated[str, Field(min_length=3, max_length=500)] | None = None


@router.post("/dispatches/{dispatch_id}/van/load")
async def van_load(
    dispatch_id: UuidIdValue, payload: LoadBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "van")
    data = await svc.load_van(db, tenant_id=claims["tenant_id"], dispatch_id=dispatch_id, lines=payload.lines, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Van loaded")


@router.get("/dispatches/{dispatch_id}/van")
async def van_summary(
    dispatch_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "van")
    return _env(await svc.summary(db, tenant_id=claims["tenant_id"], dispatch_id=dispatch_id))


@router.post("/dispatches/{dispatch_id}/van/sales")
async def van_sell(
    dispatch_id: UuidIdValue, payload: VanSaleBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "van")
    result = await svc.van_sale(
        db, tenant_id=claims["tenant_id"], dispatch_id=dispatch_id, payload=payload,
        payment_method=payload.payment_method, user_id=claims.get("sub"),
        can_override=str(claims.get("role") or "") in OVERRIDE_ROLES,
    )
    order = await orders.present_order(db, result["order"])
    order_id = result["order"].id
    await db.commit()
    payment_id = await receipt_print.newest_id(db, m.FmcgPayment, claims["tenant_id"], m.FmcgPayment.order_id, order_id)
    return _env({"order": order, "van": result["summary"], "payment_id": payment_id}, "Sold from the van")


@router.post("/dispatches/{dispatch_id}/van/losses")
async def van_loss(
    dispatch_id: UuidIdValue, payload: LossBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "van")
    data = await svc.record_loss(
        db, tenant_id=claims["tenant_id"], dispatch_id=dispatch_id, product_id=payload.product_id,
        quantity=payload.quantity, kind=payload.kind, note=payload.note, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Recorded")


@router.post("/dispatches/{dispatch_id}/van/expenses")
async def van_expense(
    dispatch_id: UuidIdValue, payload: ExpenseBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "van")
    data = await svc.record_expense(
        db, tenant_id=claims["tenant_id"], dispatch_id=dispatch_id, kind=payload.kind,
        amount=payload.amount, note=payload.note, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Recorded")


@router.post("/dispatches/{dispatch_id}/van/close")
async def van_close(
    dispatch_id: UuidIdValue, payload: CloseBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "van")
    counted = {c.product_id: c.quantity for c in payload.counted}
    data = await svc.close_van(
        db, tenant_id=claims["tenant_id"], dispatch_id=dispatch_id, counted=counted,
        counted_cash=payload.counted_cash, note=payload.note, role=str(claims.get("role") or ""),
        user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Van closed")


@router.get("/van/performance")
async def van_performance(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "reports")
    return _env(await svc.performance(db, tenant_id=claims["tenant_id"]))
