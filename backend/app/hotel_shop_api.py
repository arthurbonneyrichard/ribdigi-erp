"""Hotel shop till routes. Hotel permission and the hotel industry gate come from require_permission."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import hotel_shop as shop_svc
from app.db import get_db
from app.schemas import PartyNameValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hotel/shop", tags=["hotel-shop"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class ShopLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: float = Field(gt=0, le=999, allow_inf_nan=False)


class ShopSaleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method: Literal["cash", "card", "mobile_money", "wallet", "room"] = "cash"
    folio_id: UuidIdValue | None = None
    store_id: UuidIdValue | None = None
    customer_name: PartyNameValue | None = None
    lines: list[ShopLine] = Field(min_length=1, max_length=60)


@router.get("/items")
async def hotel_shop_items(
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await shop_svc.list_shop_items(db, claims["tenant_id"]))


@router.get("/rooms")
async def hotel_shop_rooms(
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await shop_svc.open_room_folios(db, claims["tenant_id"]))


@router.get("/sales")
async def hotel_shop_sales(
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await shop_svc.list_sales(db, claims["tenant_id"], limit=limit)
    return _env([await shop_svc.present_sale(db, row) for row in rows])


@router.get("/takings")
async def hotel_shop_takings(
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await shop_svc.shift_takings(db, claims["tenant_id"]))


@router.post("/sales")
async def hotel_shop_sell(
    payload: ShopSaleBody,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await shop_svc.create_sale(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await shop_svc.present_sale(db, row), "Sale complete")


@router.post("/sales/{sale_id}/refund")
async def hotel_shop_refund(
    sale_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await shop_svc.refund_sale(db, claims["tenant_id"], sale_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await shop_svc.present_sale(db, row), "Sale refunded")
