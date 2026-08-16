"""Cheque (check) lifecycle: pending → deposited/cleared → bounced/cancelled."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.accounting import (
    ensure_default_accounts,
    is_cheque_method,
    post_journal_entry,
)

RECEIVED = "received"
ISSUED = "issued"
PENDING = "pending"
DEPOSITED = "deposited"
CLEARED = "cleared"
BOUNCED = "bounced"
CANCELLED = "cancelled"

DIRECTIONS = frozenset({RECEIVED, ISSUED})
STATUSES = frozenset({PENDING, DEPOSITED, CLEARED, BOUNCED, CANCELLED})


def serialize_cheque(row: m.Cheque) -> dict:
    return {
        "id": row.id,
        "direction": row.direction,
        "status": row.status,
        "cheque_number": row.cheque_number,
        "amount": float(row.amount),
        "bank_name": row.bank_name,
        "cheque_date": row.cheque_date,
        "party_id": row.party_id,
        "customer_payment_id": row.customer_payment_id,
        "supplier_payment_id": row.supplier_payment_id,
        "notes": row.notes,
        "deposited_at": row.deposited_at,
        "cleared_at": row.cleared_at,
        "bounced_at": row.bounced_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def get_cheque(db: AsyncSession, tenant_id: str, cheque_id: str) -> m.Cheque:
    row = (
        await db.execute(
            select(m.Cheque).where(m.Cheque.id == cheque_id, m.Cheque.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Cheque not found")
    return row


async def list_cheques(
    db: AsyncSession,
    tenant_id: str,
    *,
    direction: str | None = None,
    status: str | None = None,
) -> list[m.Cheque]:
    # Schema ChequeDirectionValue / ChequeStatusValue reject blank/invalid → 422;
    # keep allow-list checks defense-in-depth (no silent empty equality filter).
    stmt = select(m.Cheque).where(m.Cheque.tenant_id == tenant_id)
    if direction is not None:
        d = (direction or "").strip().lower()
        if d not in DIRECTIONS:
            raise HTTPException(
                status_code=422,
                detail=f"direction must be one of: {', '.join(sorted(DIRECTIONS))}",
            )
        stmt = stmt.where(m.Cheque.direction == d)
    if status is not None:
        s = (status or "").strip().lower()
        if s not in STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"status must be one of: {', '.join(sorted(STATUSES))}",
            )
        stmt = stmt.where(m.Cheque.status == s)
    stmt = stmt.order_by(m.Cheque.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


def _cheque_number_from_payment(reference: str | None, payment_number: str) -> str:
    ref = (reference or "").strip()
    if ref:
        return ref[:50]
    return f"CHQ-{payment_number}"[:50]


async def create_from_customer_payment(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    payment: m.CustomerPayment,
    cheque_number: str | None = None,
    bank_name: str | None = None,
    cheque_date: datetime | None = None,
) -> m.Cheque | None:
    if not is_cheque_method(payment.payment_method):
        return None
    number = (cheque_number or _cheque_number_from_payment(payment.reference, payment.payment_number)).strip()
    row = m.Cheque(
        tenant_id=tenant_id,
        direction=RECEIVED,
        status=PENDING,
        cheque_number=number,
        amount=float(payment.amount),
        bank_name=bank_name,
        cheque_date=cheque_date,
        party_id=payment.customer_id,
        customer_payment_id=payment.id,
        notes=payment.notes,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def create_from_supplier_payment(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    payment: m.SupplierPayment,
    cheque_number: str | None = None,
    bank_name: str | None = None,
    cheque_date: datetime | None = None,
) -> m.Cheque | None:
    if not is_cheque_method(payment.payment_method):
        return None
    number = (cheque_number or _cheque_number_from_payment(payment.reference, payment.payment_number)).strip()
    row = m.Cheque(
        tenant_id=tenant_id,
        direction=ISSUED,
        status=PENDING,
        cheque_number=number,
        amount=float(payment.amount),
        bank_name=bank_name,
        cheque_date=cheque_date,
        party_id=payment.supplier_id,
        supplier_payment_id=payment.id,
        notes=payment.notes,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def deposit_cheque(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    cheque_id: str,
) -> m.Cheque:
    """Move received cheque from Cheques Receivable (1020) to Bank (1010)."""
    cheque = await get_cheque(db, tenant_id, cheque_id)
    if cheque.direction != RECEIVED:
        raise HTTPException(status_code=409, detail="Only received cheques can be deposited")
    if cheque.status != PENDING:
        raise HTTPException(status_code=409, detail=f"Cannot deposit cheque in status {cheque.status}")

    await ensure_default_accounts(db, tenant_id)
    amount = float(cheque.amount)
    await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Deposit cheque {cheque.cheque_number}",
        reference=cheque.cheque_number,
        source_type="cheque_deposit",
        source_id=cheque.id,
        lines=[
            {"account_code": "1010", "debit": amount, "credit": 0, "description": "Bank"},
            {"account_code": "1020", "debit": 0, "credit": amount, "description": "Cheques Receivable"},
        ],
    )
    cheque.status = DEPOSITED
    cheque.deposited_at = datetime.utcnow()
    cheque.updated_at = datetime.utcnow()
    return cheque


async def clear_cheque(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    cheque_id: str,
) -> m.Cheque:
    """Mark cleared. Issued pending cheques also post Bank out of Cheques Payable."""
    cheque = await get_cheque(db, tenant_id, cheque_id)
    amount = float(cheque.amount)
    await ensure_default_accounts(db, tenant_id)

    if cheque.direction == RECEIVED:
        if cheque.status not in {PENDING, DEPOSITED}:
            raise HTTPException(status_code=409, detail=f"Cannot clear cheque in status {cheque.status}")
        if cheque.status == PENDING:
            # Deposit + clear in one step
            await post_journal_entry(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                description=f"Clear/deposit cheque {cheque.cheque_number}",
                reference=cheque.cheque_number,
                source_type="cheque_clear",
                source_id=cheque.id,
                lines=[
                    {"account_code": "1010", "debit": amount, "credit": 0, "description": "Bank"},
                    {
                        "account_code": "1020",
                        "debit": 0,
                        "credit": amount,
                        "description": "Cheques Receivable",
                    },
                ],
            )
            cheque.deposited_at = datetime.utcnow()
        # Already deposited: money is in bank; clearing is status-only
    else:
        if cheque.status != PENDING:
            raise HTTPException(status_code=409, detail=f"Cannot clear cheque in status {cheque.status}")
        await post_journal_entry(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            description=f"Clear issued cheque {cheque.cheque_number}",
            reference=cheque.cheque_number,
            source_type="cheque_clear",
            source_id=cheque.id,
            lines=[
                {"account_code": "2015", "debit": amount, "credit": 0, "description": "Cheques Payable"},
                {"account_code": "1010", "debit": 0, "credit": amount, "description": "Bank"},
            ],
        )

    cheque.status = CLEARED
    cheque.cleared_at = datetime.utcnow()
    cheque.updated_at = datetime.utcnow()
    return cheque


async def _reverse_customer_payment(db: AsyncSession, tenant_id: str, payment: m.CustomerPayment) -> None:
    from app.fx import doc_rate, to_base
    from app.sales import get_customer, get_invoice, apply_invoice_status

    amount = float(payment.amount)
    discount = float(getattr(payment, "early_payment_discount", 0) or 0)
    settlement = round(amount + discount, 2)
    # Prefer invoice rate for base restore when linked.
    if payment.sales_invoice_id:
        inv = await get_invoice(db, tenant_id, payment.sales_invoice_id)
        settlement_base = to_base(settlement, doc_rate(inv))
    else:
        settlement_base = to_base(settlement, doc_rate(payment))
    customer = await get_customer(db, tenant_id, payment.customer_id)
    customer.balance = float(customer.balance or 0) + settlement_base

    allocations: list[tuple[str, float]] = []
    notes = payment.notes or ""
    if notes.startswith("Auto-allocated:"):
        body = notes.split(":", 1)[1].strip()
        for part in body.split(","):
            part = part.strip()
            if ":" not in part:
                continue
            inv_no, amt_s = part.rsplit(":", 1)
            try:
                allocations.append((inv_no.strip(), float(amt_s)))
            except ValueError:
                continue

    if allocations:
        for inv_no, amt in allocations:
            inv = (
                await db.execute(
                    select(m.SalesInvoice).where(
                        m.SalesInvoice.tenant_id == tenant_id,
                        m.SalesInvoice.invoice_number == inv_no,
                    )
                )
            ).scalar_one_or_none()
            if not inv:
                continue
            inv.paid_amount = max(float(inv.paid_amount or 0) - amt, 0)
            apply_invoice_status(inv)
            inv.updated_at = datetime.utcnow()
    elif payment.sales_invoice_id:
        inv = await get_invoice(db, tenant_id, payment.sales_invoice_id)
        inv.paid_amount = max(float(inv.paid_amount or 0) - settlement, 0)
        apply_invoice_status(inv)
        inv.updated_at = datetime.utcnow()


async def _reverse_supplier_payment(db: AsyncSession, tenant_id: str, payment: m.SupplierPayment) -> None:
    from app.fx import doc_rate, to_base
    from app.purchasing import get_po, get_purchase_invoice, purchase_invoice_status

    amount = float(payment.amount)
    discount = float(getattr(payment, "early_payment_discount", 0) or 0)
    settlement = round(amount + discount, 2)
    if payment.purchase_invoice_id:
        inv = await get_purchase_invoice(db, tenant_id, payment.purchase_invoice_id)
        settlement_base = to_base(settlement, doc_rate(inv))
    else:
        settlement_base = to_base(settlement, doc_rate(payment))
    supplier = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == payment.supplier_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "supplier",
            )
        )
    ).scalar_one_or_none()
    if supplier:
        supplier.balance = float(supplier.balance or 0) + settlement_base

    if payment.purchase_invoice_id:
        inv = await get_purchase_invoice(db, tenant_id, payment.purchase_invoice_id)
        inv.paid_amount = max(float(inv.paid_amount or 0) - settlement, 0)
        inv.status = purchase_invoice_status(
            float(inv.total_amount), float(inv.paid_amount), inv.due_date
        )
        inv.updated_at = datetime.utcnow()
    elif payment.purchase_order_id:
        po = await get_po(db, tenant_id, payment.purchase_order_id)
        po.paid_amount = max(float(po.paid_amount or 0) - settlement, 0)
        po.updated_at = datetime.utcnow()


async def bounce_cheque(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    cheque_id: str,
    reason: str | None = None,
) -> m.Cheque:
    """Dishonour cheque: reverse GL to AR/AP and restore document balances."""
    reason_s = (reason or "").strip()
    if not reason_s:
        raise HTTPException(status_code=400, detail="bounce reason is required")
    cheque = await get_cheque(db, tenant_id, cheque_id)
    if cheque.status in {BOUNCED, CANCELLED}:
        raise HTTPException(status_code=409, detail=f"Cheque already {cheque.status}")
    if cheque.status == CLEARED and cheque.direction == RECEIVED:
        # Cleared received: reverse Bank → AR
        pass
    elif cheque.status == CLEARED and cheque.direction == ISSUED:
        pass
    elif cheque.status not in {PENDING, DEPOSITED, CLEARED}:
        raise HTTPException(status_code=409, detail=f"Cannot bounce cheque in status {cheque.status}")

    await ensure_default_accounts(db, tenant_id)
    amount = float(cheque.amount)

    if cheque.direction == RECEIVED:
        pay_amount = amount
        discount = 0.0
        if cheque.customer_payment_id:
            payment = (
                await db.execute(
                    select(m.CustomerPayment).where(
                        m.CustomerPayment.id == cheque.customer_payment_id,
                        m.CustomerPayment.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if payment:
                discount = float(getattr(payment, "early_payment_discount", 0) or 0)
                pay_amount = float(payment.amount)
                await _reverse_customer_payment(db, tenant_id, payment)
        ar_restore = round(pay_amount + discount, 2)
        if cheque.status == PENDING:
            lines = [
                {"account_code": "1100", "debit": ar_restore, "credit": 0, "description": "AR restore"},
            ]
            if discount > 0:
                lines.append(
                    {
                        "account_code": "4100",
                        "debit": 0,
                        "credit": discount,
                        "description": "Reverse early discount",
                    }
                )
            lines.append(
                {
                    "account_code": "1020",
                    "debit": 0,
                    "credit": pay_amount,
                    "description": "Cheques Receivable",
                }
            )
        else:
            lines = [
                {"account_code": "1100", "debit": ar_restore, "credit": 0, "description": "AR restore"},
            ]
            if discount > 0:
                lines.append(
                    {
                        "account_code": "4100",
                        "debit": 0,
                        "credit": discount,
                        "description": "Reverse early discount",
                    }
                )
            lines.append(
                {"account_code": "1010", "debit": 0, "credit": pay_amount, "description": "Bank"}
            )
    else:
        pay_amount = amount
        discount = 0.0
        if cheque.supplier_payment_id:
            payment = (
                await db.execute(
                    select(m.SupplierPayment).where(
                        m.SupplierPayment.id == cheque.supplier_payment_id,
                        m.SupplierPayment.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if payment:
                discount = float(getattr(payment, "early_payment_discount", 0) or 0)
                pay_amount = float(payment.amount)
                await _reverse_supplier_payment(db, tenant_id, payment)
        ap_restore = round(pay_amount + discount, 2)
        if cheque.status == PENDING:
            # Reverse Dr AP / Cr 2015 (+ Cr 4200 if discount) → Dr 2015 (+ Dr 4200) / Cr AP
            lines = [
                {
                    "account_code": "2015",
                    "debit": pay_amount,
                    "credit": 0,
                    "description": "Cheques Payable",
                },
            ]
            if discount > 0:
                lines.append(
                    {
                        "account_code": "4200",
                        "debit": discount,
                        "credit": 0,
                        "description": "Reverse purchase discount",
                    }
                )
            lines.append(
                {"account_code": "2000", "debit": 0, "credit": ap_restore, "description": "AP restore"}
            )
        else:
            lines = [
                {"account_code": "1010", "debit": pay_amount, "credit": 0, "description": "Bank restore"},
            ]
            if discount > 0:
                lines.append(
                    {
                        "account_code": "4200",
                        "debit": discount,
                        "credit": 0,
                        "description": "Reverse purchase discount",
                    }
                )
            lines.append(
                {"account_code": "2000", "debit": 0, "credit": ap_restore, "description": "AP restore"}
            )

    await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Bounce cheque {cheque.cheque_number}: {reason_s}",
        reference=cheque.cheque_number,
        source_type="cheque_bounce",
        source_id=cheque.id,
        lines=lines,
    )
    cheque.status = BOUNCED
    cheque.bounced_at = datetime.utcnow()
    cheque.notes = ((cheque.notes or "") + f"\nBounce: {reason_s}").strip()
    cheque.updated_at = datetime.utcnow()
    return cheque


async def cancel_cheque(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    cheque_id: str,
    reason: str | None = None,
) -> m.Cheque:
    """Cancel an issued pending cheque (stop payment) before bank clearing."""
    reason_s = (reason or "").strip()
    if not reason_s:
        raise HTTPException(status_code=400, detail="cancel reason is required")
    cheque = await get_cheque(db, tenant_id, cheque_id)
    if cheque.direction != ISSUED:
        raise HTTPException(status_code=409, detail="Only issued cheques can be cancelled; use bounce for received")
    if cheque.status != PENDING:
        raise HTTPException(status_code=409, detail=f"Cannot cancel cheque in status {cheque.status}")

    await ensure_default_accounts(db, tenant_id)
    amount = float(cheque.amount)
    await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Cancel cheque {cheque.cheque_number}: {reason_s}",
        reference=cheque.cheque_number,
        source_type="cheque_cancel",
        source_id=cheque.id,
        lines=[
            {
                "account_code": "2015",
                "debit": amount,
                "credit": 0,
                "description": "Cheques Payable",
            },
            {"account_code": "2000", "debit": 0, "credit": amount, "description": "AP restore"},
        ],
    )
    if cheque.supplier_payment_id:
        payment = (
            await db.execute(
                select(m.SupplierPayment).where(
                    m.SupplierPayment.id == cheque.supplier_payment_id,
                    m.SupplierPayment.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if payment:
            await _reverse_supplier_payment(db, tenant_id, payment)

    cheque.status = CANCELLED
    cheque.notes = ((cheque.notes or "") + f"\nCancel: {reason_s}").strip()
    cheque.updated_at = datetime.utcnow()
    return cheque
