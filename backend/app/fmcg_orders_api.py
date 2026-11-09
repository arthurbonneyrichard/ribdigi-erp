"""FMCG selling routes. The `fmcg` permission and the industry gate come from require_permission."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_orders as svc
from app import models as m
from app.db import get_db
from app.schemas import (
    AddressValue,
    CreditOverrideReasonValue,
    E164PhoneValue,
    NonNegativeMoneyValue,
    PartyNameValue,
    PositiveMoneyValue,
    UuidIdValue,
)
from app.security import require_permission

router = APIRouter(prefix="/fmcg", tags=["fmcg"])

Qty = Annotated[float, Field(gt=0, le=1000000, allow_inf_nan=False)]
Method = Literal["cash", "card", "mobile_money", "bank_transfer", "cheque"]
Notes = Annotated[str, Field(min_length=1, max_length=500)]
Reason = Annotated[str, Field(min_length=3, max_length=255)]
OVERRIDE_ROLES = frozenset({"company_admin", "fmcg_manager", "super_admin"})


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class OutletBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: PartyNameValue
    phone: E164PhoneValue | None = None
    address: AddressValue | None = None
    credit_limit: NonNegativeMoneyValue = 0
    payment_terms_days: Annotated[int, Field(ge=0, le=365)] = 30
    route_id: UuidIdValue | None = None
    salesperson_name: PartyNameValue | None = None


class OrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: Qty


class OrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UuidIdValue
    terms: Literal["cash", "credit"] = "credit"
    lines: list[OrderLine] = Field(min_length=1, max_length=100)
    notes: Notes | None = None
    override_reason: CreditOverrideReasonValue | None = None


class LoadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispatch_id: UuidIdValue


class DeliverBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method: Method | None = None


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Reason


class CollectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UuidIdValue
    amount: PositiveMoneyValue
    method: Method
    order_id: UuidIdValue | None = None
    dispatch_id: UuidIdValue | None = None
    notes: Notes | None = None


class ReturnLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_id: UuidIdValue
    quantity: Qty


class ReturnBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: list[ReturnLine] = Field(min_length=1, max_length=100)
    reason: Literal["damaged", "expired", "unsold", "wrong_item", "other"]
    resaleable: bool = False


class SettleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted_cash: NonNegativeMoneyValue


@router.get("/today")
async def fmcg_today(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    data = await svc.today(db, claims["tenant_id"])
    if str(claims.get("role") or "") == "fmcg_driver":
        for key in ("sales_today", "sales_yesterday", "owed_total", "owed_late", "trend"):
            data.pop(key, None)
        data["attention"] = [a for a in data.get("attention", []) if "owed" not in a["text"] and "credit" not in a["text"]]
    return _env(data)


@router.get("/products-for-sale")
async def fmcg_products(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select

    rows = (
        await db.execute(
            select(m.Product)
            .where(m.Product.tenant_id == claims["tenant_id"], m.Product.is_active.is_(True), m.Product.selling_price > 0)
            .order_by(m.Product.name.asc())
        )
    ).scalars()
    return _env(
        [
            {"id": r.id, "name": r.name, "price": float(r.selling_price or 0), "stock_qty": float(r.stock_qty or 0)}
            for r in rows
        ]
    )


@router.get("/outlets")
async def fmcg_outlets(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    return _env(await svc.list_outlets(db, claims["tenant_id"]))


@router.post("/outlets")
async def fmcg_outlet_create(
    payload: OutletBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "outlets")
    row = await svc.create_outlet(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env({"id": row.id, "name": row.name}, "Outlet added")


@router.get("/orders")
async def fmcg_orders(
    show: Annotated[str, Query(pattern="^(open|all|booked|loaded|delivered|cancelled)$")] = "open",
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await svc.list_orders(db, claims["tenant_id"], show=show)
    return _env([await svc.present_order(db, row) for row in rows])


@router.post("/orders")
async def fmcg_order_create(
    payload: OrderBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "orders")
    row = await svc.create_order(
        db, claims["tenant_id"], payload, user_id=claims.get("sub"),
        can_override=str(claims.get("role") or "") in OVERRIDE_ROLES,
    )
    await db.commit()
    return _env(await svc.present_order(db, row), "Order booked")


@router.post("/orders/{order_id}/load")
async def fmcg_order_load(
    order_id: UuidIdValue,
    payload: LoadBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "dispatch")
    row = await svc.load_order(db, claims["tenant_id"], order_id, dispatch_id=payload.dispatch_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_order(db, row), "Order loaded")


@router.post("/orders/{order_id}/deliver")
async def fmcg_order_deliver(
    order_id: UuidIdValue,
    payload: DeliverBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "deliver")
    row = await svc.deliver_order(
        db, claims["tenant_id"], order_id, payment_method=payload.payment_method, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(await svc.present_order(db, row), "Delivered")


@router.post("/orders/{order_id}/failed")
async def fmcg_order_failed(
    order_id: UuidIdValue,
    payload: ReasonBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "deliver")
    row = await svc.fail_delivery(db, claims["tenant_id"], order_id, reason=payload.reason, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_order(db, row), "Sent back to be loaded again")


@router.post("/orders/{order_id}/cancel")
async def fmcg_order_cancel(
    order_id: UuidIdValue,
    payload: ReasonBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "correct")
    row = await svc.cancel_order(db, claims["tenant_id"], order_id, reason=payload.reason, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_order(db, row), "Order cancelled")


@router.post("/orders/{order_id}/returns")
async def fmcg_order_return(
    order_id: UuidIdValue,
    payload: ReturnBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "returns")
    row = await svc.create_return(
        db, claims["tenant_id"], order_id, lines=payload.lines, reason=payload.reason,
        resaleable=payload.resaleable, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(await svc.present_return(db, row), "Return recorded")


@router.get("/returns")
async def fmcg_returns(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    rows = await svc.list_returns(db, claims["tenant_id"])
    return _env([await svc.present_return(db, row) for row in rows])


@router.get("/collections")
async def fmcg_collections(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    rows = await svc.list_payments(db, claims["tenant_id"])
    return _env([await svc.present_payment(db, row) for row in rows])


@router.post("/collections")
async def fmcg_collect(
    payload: CollectBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "collect")
    row = await svc.collect(
        db, claims["tenant_id"], customer_id=payload.customer_id, amount=payload.amount, method=payload.method,
        order_id=payload.order_id, dispatch_id=payload.dispatch_id, notes=payload.notes, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(await svc.present_payment(db, row), "Payment recorded")


@router.get("/dispatches/{dispatch_id}/cash")
async def fmcg_dispatch_cash(
    dispatch_id: UuidIdValue,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "dispatch")
    return _env({"expected_cash": await svc.expected_cash(db, claims["tenant_id"], dispatch_id)})


@router.post("/dispatches/{dispatch_id}/settle")
async def fmcg_dispatch_settle(
    dispatch_id: UuidIdValue,
    payload: SettleBody,
    claims=Depends(require_permission("fmcg", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "dispatch")
    data = await svc.settle_dispatch(
        db, claims["tenant_id"], dispatch_id, counted_cash=payload.counted_cash, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Dispatch settled")


@router.get("/reports")
async def fmcg_reports(
    start_date: date | None = None,
    end_date: date | None = None,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "correct")
    end = end_date or date.today()
    start = start_date or end - timedelta(days=6)
    data = await svc.period_numbers(db, claims["tenant_id"], start=start, end=end)
    data["aging"] = await svc.aging(db, claims["tenant_id"])
    return _env(data)
