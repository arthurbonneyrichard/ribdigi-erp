"""Retail till routes: held sales, layaway, serial numbers."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import pos_extras as svc
from app.db import get_db
from app.schemas import E164PhoneValue, IsoDateQueryValue, NonNegativeMoneyValue, PositiveMoneyValue, PositiveQtyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/pos", tags=["pos-extras"])
serial_router = APIRouter(prefix="/inventory/serials", tags=["serials"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class HeldCartLine(BaseModel):
    model_config = ConfigDict(extra="allow")

    product_id: UuidIdValue
    quantity: PositiveQtyValue
    unit_price: NonNegativeMoneyValue = 0


class HoldSaleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Annotated[str, Field(min_length=1, max_length=120)]
    store_id: UuidIdValue | None = None
    items: list[HeldCartLine] = Field(min_length=1, max_length=300)
    customer_id: UuidIdValue | None = None
    discount_amount: NonNegativeMoneyValue = 0


@router.get("/held")
async def pos_held(
    store_id: Annotated[UuidIdValue | None, Query()] = None,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await svc.list_held(db, tenant_id=claims["tenant_id"], store_id=store_id)
    return _env([svc.serialize_held(r) for r in rows])


@router.post("/held")
async def pos_hold(
    payload: HoldSaleBody,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    cart = payload.model_dump(mode="json", exclude={"label", "store_id"})
    row = await svc.hold_sale(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), store_id=payload.store_id, label=payload.label, cart=cart
    )
    await db.commit()
    return _env(svc.serialize_held(row), "Sale on hold")


@router.post("/held/{held_id}/take")
async def pos_take_held(
    held_id: UuidIdValue,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await svc.take_held(db, tenant_id=claims["tenant_id"], held_id=held_id)
    body = svc.serialize_held(row)
    await db.commit()
    return _env(body, "Sale picked up")


class LayawayLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    quantity: PositiveQtyValue


Method = Literal["cash", "card", "mobile_money", "bank_transfer", "wallet"]


class LayawayOpenBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: UuidIdValue | None = None
    customer_id: UuidIdValue | None = None
    customer_name: Annotated[str, Field(min_length=1, max_length=180)] | None = None
    phone: E164PhoneValue | None = None
    items: list[LayawayLine] = Field(min_length=1, max_length=100)
    due_date: IsoDateQueryValue | None = None
    notes: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    deposit: NonNegativeMoneyValue = 0
    deposit_method: Method = "cash"
    deposit_reference: Annotated[str, Field(min_length=4, max_length=100)] | None = None


class LayawayPayBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: PositiveMoneyValue
    method: Method = "cash"
    reference: Annotated[str, Field(min_length=4, max_length=100)] | None = None


class LayawayCancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=255)]
    keep: NonNegativeMoneyValue = 0
    refund_method: Method = "cash"


async def _present(db, tenant_id: str, row) -> dict:
    return svc.serialize_layaway(row, await svc.layaway_payments(db, tenant_id, row.id))


@router.get("/layaways")
async def pos_layaways(
    status: Annotated[Literal["open", "completed", "cancelled"] | None, Query()] = None,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await svc.list_layaways(db, tenant_id=claims["tenant_id"], status=status)
    return _env([svc.serialize_layaway(r) for r in rows])


@router.post("/layaways")
async def pos_layaway_open(
    payload: LayawayOpenBody,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.reports import parse_date

    row = await svc.open_layaway(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        store_id=payload.store_id,
        customer_id=payload.customer_id,
        customer_name=payload.customer_name,
        phone=payload.phone,
        items=[i.model_dump() for i in payload.items],
        due_date=parse_date(payload.due_date).date() if payload.due_date else None,
        notes=payload.notes,
        deposit=payload.deposit,
        deposit_method=payload.deposit_method,
        deposit_reference=payload.deposit_reference,
    )
    await audit_svc.record_event(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), module="pos", action="layaway_opened",
        entity="pos_layaway", entity_id=row.id, details={"number": row.layaway_number, "total": row.total},
    )
    await db.commit()
    return _env(await _present(db, claims["tenant_id"], row), f"Layaway {row.layaway_number} opened. The goods are set aside.")


@router.get("/layaways/{layaway_id}")
async def pos_layaway_get(
    layaway_id: UuidIdValue,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    row = await svc._layaway(db, claims["tenant_id"], layaway_id)
    return _env(await _present(db, claims["tenant_id"], row))


@router.post("/layaways/{layaway_id}/payments")
async def pos_layaway_pay(
    layaway_id: UuidIdValue,
    payload: LayawayPayBody,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await svc.pay_layaway(
        db, tenant_id=claims["tenant_id"], layaway_id=layaway_id, amount=payload.amount,
        method=payload.method, reference=payload.reference, user_id=claims.get("sub"),
    )
    await db.commit()
    message = "Paid in full. Hand over the goods." if row.status == "completed" else "Payment recorded"
    return _env(await _present(db, claims["tenant_id"], row), message)


@router.post("/layaways/{layaway_id}/cancel")
async def pos_layaway_cancel(
    layaway_id: UuidIdValue,
    payload: LayawayCancelBody,
    claims=Depends(require_permission("pos", "approve")),
    db: AsyncSession = Depends(get_db),
):
    row = await svc.cancel_layaway(
        db, tenant_id=claims["tenant_id"], layaway_id=layaway_id, keep=payload.keep,
        refund_method=payload.refund_method, reason=payload.reason, user_id=claims.get("sub"),
    )
    await audit_svc.record_event(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), module="pos", action="layaway_cancelled",
        entity="pos_layaway", entity_id=row.id, details={"number": row.layaway_number, "kept": payload.keep, "reason": payload.reason},
    )
    await db.commit()
    return _env(await _present(db, claims["tenant_id"], row), "Layaway cancelled. The goods are back on sale.")


@serial_router.get("")
async def serials_find(
    q: Annotated[str | None, Query(max_length=80)] = None,
    product_id: Annotated[UuidIdValue | None, Query()] = None,
    status: Annotated[Literal["in_stock", "sold", "returned"] | None, Query()] = None,
    claims=Depends(require_permission("inventory", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await svc.find_serials(db, tenant_id=claims["tenant_id"], q=q, product_id=product_id, status=status)
    return _env([svc.serialize_serial(r, name) for r, name in rows])
