"""Hotel guest invoice routes. Hotel permission and the hotel industry gate come from require_permission."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app import hotel_invoices as invoices_svc
from app.db import get_db
from app.schemas import PaymentReferenceValue, PositiveMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hotel/invoices", tags=["hotel-invoices"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class GuestPaymentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: PositiveMoneyValue
    method: Literal["cash", "momo", "card", "bank", "cheque"] = "cash"
    reference: PaymentReferenceValue | None = None


@router.get("")
async def hotel_invoices(
    show: Annotated[Literal["owed", "all"], Query()] = "owed",
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await invoices_svc.list_invoices(db, claims["tenant_id"], show=show))


@router.post("/{invoice_id}/payments")
async def hotel_invoice_payment(
    invoice_id: UuidIdValue,
    payload: GuestPaymentBody,
    claims=Depends(require_permission("hotel", "write")),
    db: AsyncSession = Depends(get_db),
):
    body = await invoices_svc.take_payment(
        db,
        claims["tenant_id"],
        invoice_id,
        user_id=claims["sub"],
        amount=payload.amount,
        method=payload.method,
        reference=payload.reference,
    )
    await db.commit()
    return _env(body, "Payment recorded")


@router.get("/{invoice_id}/print")
async def hotel_invoice_print(
    invoice_id: UuidIdValue,
    claims=Depends(require_permission("hotel", "read")),
    db: AsyncSession = Depends(get_db),
):
    html = await invoices_svc.print_html(db, claims["tenant_id"], invoice_id)
    return Response(content=html, media_type="text/html; charset=utf-8")
