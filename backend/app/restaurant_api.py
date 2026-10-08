"""Restaurant HTTP routes. Permission and industry gates stay in require_permission."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import restaurant as restaurant_svc
from app.db import get_db
from app.security import require_permission

router = APIRouter(prefix="/restaurant", tags=["restaurant"])


class TableBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    seats: int = 2
    store_id: str | None = None


class ModifierGroupBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)


class ModifierBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    price: Decimal = Decimal("0")


class RecipeLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: str
    quantity: Decimal


class RecipeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    name: str = Field(min_length=1, max_length=160)
    lines: list[RecipeLineBody] = Field(default_factory=list)


class OrderLineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str
    quantity: Decimal
    unit_price: Decimal | None = None
    modifier_ids: list[str] = Field(default_factory=list)


class OrderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_mode: str
    payment_method: str = "cash"
    store_id: str | None = None
    table_id: str | None = None
    customer_name: str | None = None
    notes: str | None = None
    lines: list[OrderLineBody]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


@router.get("/summary")
async def restaurant_summary(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.summary(db, claims["tenant_id"], user_id=claims.get("sub")))


@router.get("/tables")
async def restaurant_tables(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await restaurant_svc.list_tables(db, claims["tenant_id"], user_id=claims.get("sub"))
    return _env([restaurant_svc.serialize_table(row) for row in rows])


@router.post("/tables")
async def restaurant_create_table(
    payload: TableBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_table(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(restaurant_svc.serialize_table(row), "Table saved")


@router.post("/modifier-groups")
async def restaurant_modifier_group(
    payload: ModifierGroupBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_modifier_group(db, claims["tenant_id"], payload.name)
    await db.commit()
    return _env({"id": row.id, "name": row.name}, "Modifier group saved")


@router.post("/modifier-groups/{group_id}/modifiers")
async def restaurant_modifier(
    group_id: str,
    payload: ModifierBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.add_modifier(
        db, claims["tenant_id"], group_id, name=payload.name, price=payload.price
    )
    await db.commit()
    return _env({"id": row.id, "name": row.name, "price": float(row.price or 0)}, "Modifier saved")


@router.post("/recipes")
async def restaurant_recipe(
    payload: RecipeBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_recipe(db, claims["tenant_id"], payload)
    await db.commit()
    return _env({"id": row.id, "product_id": row.product_id, "name": row.name}, "Recipe saved")


@router.get("/orders")
async def restaurant_orders(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await restaurant_svc.list_orders(db, claims["tenant_id"], user_id=claims.get("sub"))
    return _env([restaurant_svc.serialize_order(row) for row in rows])


@router.post("/orders")
async def restaurant_create_order(
    payload: OrderBody,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.create_order(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order saved")


@router.post("/orders/{order_id}/send")
async def restaurant_send(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.send_to_kitchen(db, claims["tenant_id"], order_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Sent to kitchen")


@router.post("/orders/{order_id}/complete")
async def restaurant_complete(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.complete_order(db, claims["tenant_id"], order_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order completed")


@router.post("/orders/{order_id}/cancel")
async def restaurant_cancel(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.cancel_order(
        db, claims["tenant_id"], order_id, user_id=claims.get("sub"), void=False
    )
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order cancelled")


@router.post("/orders/{order_id}/void")
async def restaurant_void(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.cancel_order(
        db, claims["tenant_id"], order_id, user_id=claims.get("sub"), void=True
    )
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order voided")


@router.post("/orders/{order_id}/refund")
async def restaurant_refund(
    order_id: str,
    claims=Depends(require_permission("restaurant", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await restaurant_svc.refund_order(db, claims["tenant_id"], order_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(restaurant_svc.serialize_order(row), "Order refunded")


@router.get("/kitchen")
async def restaurant_kitchen(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await restaurant_svc.list_kitchen(db, claims["tenant_id"], user_id=claims.get("sub"))
    return _env([restaurant_svc.serialize_ticket(row) for row in rows])


@router.get("/reports")
async def restaurant_reports(
    claims=Depends(require_permission("restaurant", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await restaurant_svc.reports(db, claims["tenant_id"], user_id=claims.get("sub")))
