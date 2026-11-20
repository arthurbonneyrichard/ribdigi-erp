"""Routes for the gym shop. Selling: front desk and managers (`desk`). Products and stock: managers (`correct`)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_shop as svc
from app.db import get_db
from app.schemas import NonNegativeMoneyValue, PositiveMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym/shop", tags=["gym"])
Method = Literal["cash", "card", "mobile_money", "bank_transfer"]
RestockMethod = Literal["cash", "card", "mobile_money", "bank_transfer", "credit"]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class ProductBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=150)]
    sku: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    price: NonNegativeMoneyValue
    reorder_level: Annotated[int, Field(ge=0, le=100000)] = 0


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: NonNegativeMoneyValue | None = None
    reorder_level: Annotated[int, Field(ge=0, le=100000)] | None = None
    is_active: bool | None = None


class RestockBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    quantity: Annotated[int, Field(ge=1, le=100000)]
    unit_cost: PositiveMoneyValue
    method: RestockMethod
    supplier_name: Annotated[str, Field(min_length=1, max_length=150)] | None = None
    due_on: date | None = None


class BillPay(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Method


class RefundBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: Annotated[list["ItemBody"], Field(min_length=1, max_length=50)]
    method: Method


class ItemBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UuidIdValue
    quantity: Annotated[int, Field(ge=1, le=1000)]


class SaleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: Annotated[list[ItemBody], Field(min_length=1, max_length=50)]
    method: Method
    member_id: UuidIdValue | None = None


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


@router.get("/products")
async def products(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "desk")
    return _env(await svc.list_products(db, claims["tenant_id"]))


@router.post("/products")
async def product_add(payload: ProductBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.create_product(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Product added")


@router.post("/products/{product_id}")
async def product_update(product_id: UuidIdValue, payload: ProductUpdate, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.update_product(db, claims["tenant_id"], product_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.post("/products/{product_id}/restock")
async def product_restock(product_id: UuidIdValue, payload: RestockBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.restock(db, claims["tenant_id"], product_id, quantity=payload.quantity, unit_cost=payload.unit_cost, method=payload.method,
        supplier_name=payload.supplier_name, due_on=payload.due_on, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Stock added")


@router.post("/sales")
async def sale(payload: SaleBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "desk")
    data = await svc.sell(db, claims["tenant_id"], items=payload.items, method=payload.method, member_id=payload.member_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Sold")


@router.get("/sales")
async def sales(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "desk")
    return _env(await svc.list_sales(db, claims["tenant_id"]))


@router.post("/sales/{sale_id}/refund")
async def sale_refund(sale_id: UuidIdValue, payload: RefundBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")  # a refund is a manager's decision
    data = await svc.refund(db, claims["tenant_id"], sale_id, items=payload.items, method=payload.method, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Refunded")


@router.get("/bills")
async def bills(status: Literal["open", "paid"] | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env(await svc.list_bills(db, claims["tenant_id"], status=status))


@router.post("/bills/{bill_id}/pay")
async def bill_pay(bill_id: UuidIdValue, payload: BillPay, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.pay_bill(db, claims["tenant_id"], bill_id, method=payload.method, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Bill paid")


RefundBody.model_rebuild()
