"""Hotel guest invoices: the invoice each folio becomes at check-out, what is still owed, and payments.

The shared sales engine keeps the invoice and the books (customer payment, receivables journal);
this module only reads and pays hotel folio invoices in hotel words, under the hotel permission.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import sales as sales_svc
from app.honesty import money_json

# Hotel tender words → the shared settlement methods.
PAY_METHODS = {"cash": "cash", "momo": "mobile_money", "card": "card", "bank": "bank_transfer", "cheque": "cheque"}


def _due(invoice: m.SalesInvoice) -> float:
    return max(0.0, money_json(round(float(invoice.total_amount or 0) - float(invoice.paid_amount or 0), 2)))


async def list_invoices(db: AsyncSession, tenant_id: str, *, show: str = "owed") -> dict:
    rows = (
        await db.execute(
            select(m.HotelFolio, m.SalesInvoice, m.HotelGuest, m.HotelReservation, m.HotelRoom)
            .join(m.SalesInvoice, m.SalesInvoice.id == m.HotelFolio.sales_invoice_id)
            .join(m.HotelGuest, m.HotelGuest.id == m.HotelFolio.guest_id)
            .join(m.HotelReservation, m.HotelReservation.id == m.HotelFolio.reservation_id)
            .outerjoin(m.HotelRoom, m.HotelRoom.id == m.HotelReservation.room_id)
            .where(m.HotelFolio.tenant_id == tenant_id, m.SalesInvoice.tenant_id == tenant_id)
            .order_by(m.SalesInvoice.created_at.desc())
            .limit(300)
        )
    ).all()
    items = []
    for folio, invoice, guest, reservation, room in rows:
        due = _due(invoice)
        if invoice.status == "cancelled" or (show == "owed" and due <= 0.004):
            continue
        items.append(
            {
                "id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "status": invoice.status,
                "total": money_json(invoice.total_amount),
                "paid": money_json(invoice.paid_amount),
                "due": due,
                "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
                "folio_number": folio.folio_number,
                "reservation_number": reservation.reservation_number,
                "check_in": reservation.check_in_date.isoformat() if reservation.check_in_date else None,
                "check_out": reservation.check_out_date.isoformat() if reservation.check_out_date else None,
                "room": (room.code if room else None),
                "guest_id": guest.id,
                "guest_name": guest.full_name,
                "company_name": guest.company_name,
                "phone": guest.phone,
                "email": guest.email,
            }
        )
    owed = [i for i in items if i["due"] > 0.004]
    return {
        "items": items,
        "owed_total": money_json(round(sum(i["due"] for i in owed), 2)),
        "owed_count": len(owed),
    }


async def _hotel_invoice(db: AsyncSession, tenant_id: str, invoice_id: str) -> m.SalesInvoice:
    folio = (
        await db.execute(
            select(m.HotelFolio).where(m.HotelFolio.tenant_id == tenant_id, m.HotelFolio.sales_invoice_id == invoice_id)
        )
    ).scalar_one_or_none()
    invoice = await db.get(m.SalesInvoice, invoice_id)
    if folio is None or invoice is None or invoice.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Guest invoice not found")
    return invoice


async def take_payment(
    db: AsyncSession,
    tenant_id: str,
    invoice_id: str,
    *,
    user_id: str,
    amount: float,
    method: str,
    reference: str | None,
) -> dict:
    invoice = await _hotel_invoice(db, tenant_id, invoice_id)
    due = _due(invoice)
    if due <= 0.004:
        raise HTTPException(status_code=409, detail="This invoice is already paid")
    if money_json(amount) > due + 0.004:
        raise HTTPException(status_code=422, detail=f"That is more than the {due:.2f} still owed")
    payment = await sales_svc.record_customer_payment(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=invoice.customer_id,
        amount=amount,
        sales_invoice_id=invoice.id,
        payment_method=PAY_METHODS.get(method, "cash"),
        reference=reference,
    )
    await db.refresh(invoice)
    return {
        "invoice_id": invoice.id,
        "payment_id": payment.id,
        "paid": money_json(invoice.paid_amount),
        "due": _due(invoice),
        "status": invoice.status,
        "at": datetime.utcnow().isoformat(),
    }


async def print_html(db: AsyncSession, tenant_id: str, invoice_id: str) -> str:
    from app import invoice_print as invoice_print_svc
    from app import tenants as tenants_svc

    await _hotel_invoice(db, tenant_id, invoice_id)
    payload = await invoice_print_svc.build_invoice_print_payload(db, tenant_id=tenant_id, invoice_id=invoice_id)
    tenant = await tenants_svc.get_tenant(db, tenant_id)
    return invoice_print_svc.render_invoice_a4_html(payload, tenant=tenant)
