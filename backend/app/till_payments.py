"""Mobile Money at the till, charged through the company's own Paystack account.

The cashier types the customer's number; Paystack sends a prompt to the phone; the customer
approves it. The till asks for the status until it is paid, then completes the sale with that
reference. The sale checks the reference is paid, for at least the amount, and not used before,
so a prompt can only ever pay once. Keys come from the company's payment settings (the same
Paystack account as the web shop). Card payments stay on the bank's card machine and are recorded.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings
from app.honesty import money_json

PAYSTACK = "https://api.paystack.co"
PROVIDERS = {"mtn": "mtn", "telecel": "vod", "vodafone": "vod", "airteltigo": "atl", "at": "atl"}
DESKS = frozenset({"retail", "restaurant", "hotel", "bakery", "gym"})
TIMEOUT = 20


def _production() -> bool:
    return (settings.APP_ENV or "").strip().lower() == "production"


def serialize(row: m.TillPaymentIntent) -> dict:
    return {
        "reference": row.reference,
        "desk": row.desk,
        "amount": money_json(row.amount),
        "currency": row.currency,
        "phone": row.phone_hint,
        "provider": row.provider,
        "status": row.status,
        "paid": row.status == "success",
        "message": row.message,
        "used": bool(row.used_ref),
    }


async def _gateway(db: AsyncSession, tenant_id: str) -> tuple[str, str | None]:
    """('paystack', secret) or ('mock', None) outside production when nothing is set up."""
    from app.ecommerce_payments import get_gateway
    from app.ecommerce_secrets import decrypt_ecommerce_secret

    row = await get_gateway(db, tenant_id)
    if row is not None and row.provider == "paystack" and row.secret_enc:
        return "paystack", decrypt_ecommerce_secret(row.secret_enc)
    if _production():
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MOMO_NOT_SET_UP",
                "message": "Mobile Money prompts need your Paystack account. Add the secret key under Online shop → Payments.",
            },
        )
    return "mock", None


def _local_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("233") and len(digits) == 12:
        digits = "0" + digits[3:]
    if not re.fullmatch(r"0\d{9}", digits):
        raise HTTPException(status_code=422, detail="Enter the customer's 10-digit Mobile Money number")
    return digits


async def _call(secret: str, method: str, path: str, body: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        res = await client.request(
            method, f"{PAYSTACK}{path}", json=body, headers={"Authorization": f"Bearer {secret}"}
        )
    try:
        data = res.json()
    except ValueError:
        data = {}
    if res.status_code >= 500:
        raise HTTPException(status_code=502, detail="Paystack is not answering. Try again or take another payment.")
    return data if isinstance(data, dict) else {}


def _apply(row: m.TillPaymentIntent, data: dict) -> None:
    status = str((data.get("data") or {}).get("status") or "").lower()
    paid_minor = (data.get("data") or {}).get("amount")
    text = str((data.get("data") or {}).get("display_text") or (data.get("data") or {}).get("gateway_response") or data.get("message") or "")
    if status == "success":
        if paid_minor is not None and int(paid_minor) + 1 < int(round(money_json(row.amount) * 100)):
            row.status = "failed"
            row.message = "Paid less than asked"
        else:
            row.status = "success"
            row.message = "Paid"
    elif status in {"failed", "abandoned", "reversed"}:
        row.status = "failed"
        row.message = (text or "The customer did not approve").strip()[:255]
    elif status == "send_otp":
        row.status = "otp"
        row.message = (text or "Ask the customer for the code sent to their phone").strip()[:255]
    else:
        row.status = "pending"
        row.message = (text or "Waiting for the customer to approve on their phone").strip()[:255]
    row.updated_at = datetime.utcnow()


async def start(
    db: AsyncSession,
    *,
    tenant_id: str,
    amount: float,
    phone: str,
    provider: str,
    desk: str,
    email: str | None = None,
    user_id: str | None = None,
) -> m.TillPaymentIntent:
    amt = money_json(amount)
    if amt <= 0:
        raise HTTPException(status_code=422, detail="Enter the amount to charge")
    network = PROVIDERS.get((provider or "").strip().lower())
    if not network:
        raise HTTPException(status_code=422, detail="Pick MTN, Telecel or AirtelTigo")
    if desk not in DESKS:
        raise HTTPException(status_code=422, detail="Unknown till")
    local = _local_phone(phone)
    kind, secret = await _gateway(db, tenant_id)
    tenant = await db.get(m.Tenant, tenant_id)
    row = m.TillPaymentIntent(
        tenant_id=tenant_id,
        reference=f"till_{secrets.token_hex(12)}",
        desk=desk,
        amount=amt,
        currency=(getattr(tenant, "currency", None) or "GHS")[:3],
        phone_hint=f"{local[:3]}****{local[-3:]}",
        provider=network,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    if kind == "mock":
        row.status = "pending"
        row.message = "Test mode: no real prompt was sent. Check status to mark it paid."
        return row
    payer = (email or getattr(tenant, "email", None) or "").strip() or f"till@{(tenant.slug if tenant else 'shop')}.ribdigi.com"
    data = await _call(
        secret or "",
        "POST",
        "/charge",
        {
            "email": payer,
            "amount": int(round(amt * 100)),
            "currency": row.currency,
            "reference": row.reference,
            "mobile_money": {"phone": local, "provider": network},
            "metadata": {"source": "ribdigi_till", "desk": desk},
        },
    )
    if data.get("status") is False:
        row.status = "failed"
        row.message = str(data.get("message") or "Paystack refused the charge")[:255]
    else:
        _apply(row, data)
    await db.flush()
    return row


async def _intent(db: AsyncSession, tenant_id: str, reference: str) -> m.TillPaymentIntent:
    row = (
        await db.execute(
            select(m.TillPaymentIntent).where(
                m.TillPaymentIntent.tenant_id == tenant_id, m.TillPaymentIntent.reference == reference
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Mobile Money payment not found")
    return row


async def check(db: AsyncSession, *, tenant_id: str, reference: str) -> m.TillPaymentIntent:
    row = await _intent(db, tenant_id, reference)
    if row.status in {"success", "failed"}:
        return row
    kind, secret = await _gateway(db, tenant_id)
    if kind == "mock":
        row.status = "success"
        row.message = "Test mode: marked paid"
        row.updated_at = datetime.utcnow()
    else:
        _apply(row, await _call(secret or "", "GET", f"/transaction/verify/{row.reference}"))
    await db.flush()
    return row


async def submit_otp(db: AsyncSession, *, tenant_id: str, reference: str, otp: str) -> m.TillPaymentIntent:
    row = await _intent(db, tenant_id, reference)
    if row.status != "otp":
        return row
    kind, secret = await _gateway(db, tenant_id)
    if kind == "mock":
        row.status = "success"
        row.message = "Test mode: marked paid"
    else:
        _apply(row, await _call(secret or "", "POST", "/charge/submit_otp", {"otp": otp, "reference": row.reference}))
    await db.flush()
    return row


async def claim(db: AsyncSession, *, tenant_id: str, reference: str, amount: float, used_ref: str) -> None:
    """A sale that says it was paid by a Mobile Money prompt: check it was, then use it up."""
    if not str(reference or "").startswith("till_"):
        return  # a typed MoMo transaction ID from the customer's phone, recorded as it is
    row = await _intent(db, tenant_id, reference)
    if row.status != "success":
        row = await check(db, tenant_id=tenant_id, reference=reference)
    if row.status != "success":
        raise HTTPException(status_code=409, detail="That Mobile Money payment is not approved yet")
    if row.used_ref and row.used_ref != used_ref:
        raise HTTPException(status_code=409, detail="That Mobile Money payment has already paid another sale")
    if money_json(amount) > money_json(row.amount) + 0.009:
        raise HTTPException(status_code=409, detail=f"The prompt was for {money_json(row.amount):.2f}, less than this part")
    row.used_ref = used_ref[:80]
    row.updated_at = datetime.utcnow()
    await db.flush()
