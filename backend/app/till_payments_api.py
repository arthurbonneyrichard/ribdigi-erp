"""Mobile Money prompt routes, one set per desk so each desk's own staff rules apply.

Retail: /pos/momo   Restaurant: /restaurant/till/momo   Hotel: /hotel/momo   Bakery: /bakery/till/momo
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import till_payments as svc
from app.db import get_db
from app.schemas import PositiveMoneyValue
from app.security import require_permission


class MomoStartBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: PositiveMoneyValue
    phone: Annotated[str, Field(min_length=9, max_length=20)]
    provider: Literal["mtn", "telecel", "vodafone", "airteltigo", "at"]
    email: EmailStr | None = None


class MomoOtpBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    otp: Annotated[str, Field(min_length=3, max_length=10, pattern=r"^[0-9]+$")]


Reference = Annotated[str, Path(min_length=8, max_length=64, pattern=r"^till_[0-9a-f]+$")]


# Roles whose job is not taking money: they cannot send a payment prompt.
NO_PAYMENT_ROLES = frozenset(
    {"restaurant_waiter", "restaurant_kitchen", "bakery_baker", "hotel_housekeeping", "hotel_maintenance", "hotel_reservations"}
)


def _may_take_money(claims: dict) -> None:
    from fastapi import HTTPException

    if str(claims.get("role") or "") in NO_PAYMENT_ROLES:
        raise HTTPException(status_code=403, detail="Taking payment needs a cashier or manager.")


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def build(prefix: str, module: str, desk: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["till-payments"])

    @router.post("/momo")
    async def momo_start(
        payload: MomoStartBody,
        claims=Depends(require_permission(module, "write")),
        db: AsyncSession = Depends(get_db),
    ):
        _may_take_money(claims)
        row = await svc.start(
            db,
            tenant_id=claims["tenant_id"],
            amount=payload.amount,
            phone=payload.phone,
            provider=payload.provider,
            desk=desk,
            email=str(payload.email) if payload.email else None,
            user_id=claims.get("sub"),
        )
        await audit_svc.record_event(
            db,
            tenant_id=claims["tenant_id"],
            user_id=claims.get("sub"),
            module=module if module != "pos" else "pos",
            action="momo_prompt_sent",
            entity="till_payment",
            entity_id=row.id,
            details={"amount": row.amount, "desk": desk, "status": row.status},
        )
        await db.commit()
        return _env(svc.serialize(row), row.message or "Prompt sent")

    @router.get("/momo/{reference}")
    async def momo_status(
        reference: Reference,
        claims=Depends(require_permission(module, "write")),
        db: AsyncSession = Depends(get_db),
    ):
        row = await svc.check(db, tenant_id=claims["tenant_id"], reference=reference)
        await db.commit()
        return _env(svc.serialize(row), row.message or row.status)

    @router.post("/momo/{reference}/otp")
    async def momo_otp(
        reference: Reference,
        payload: MomoOtpBody,
        claims=Depends(require_permission(module, "write")),
        db: AsyncSession = Depends(get_db),
    ):
        row = await svc.submit_otp(db, tenant_id=claims["tenant_id"], reference=reference, otp=payload.otp)
        await db.commit()
        return _env(svc.serialize(row), row.message or row.status)

    return router


ROUTERS = [
    build("/pos", "pos", "retail"),
    build("/restaurant/till", "restaurant", "restaurant"),
    build("/hotel", "hotel", "hotel"),
    build("/bakery/till", "bakery", "bakery"),
]
