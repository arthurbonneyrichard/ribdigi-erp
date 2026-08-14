"""POS shift / session management and cash reconciliation."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.doc_numbers import next_pos_sale_number, next_pos_session_number  # re-exported for API callers


def compute_expected_cash(opening_cash: float, cash_sales: float) -> float:
    return round(float(opening_cash or 0) + float(cash_sales or 0), 2)


def compute_variance(actual_cash: float, expected_cash: float) -> float:
    return round(float(actual_cash) - float(expected_cash), 2)


def normalize_payment_method(method: str | None) -> str:
    value = (method or "cash").strip().lower()
    if value in {"cash", "card", "wallet", "credit", "other"}:
        return value
    return "other"


async def next_session_number(db: AsyncSession, tenant_id: str) -> str:
    return await next_pos_session_number(db, tenant_id)


async def get_session(db: AsyncSession, tenant_id: str, session_id: str) -> m.PosSession:
    session = (
        await db.execute(
            select(m.PosSession).where(
                m.PosSession.id == session_id,
                m.PosSession.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="POS session not found")
    return session


async def get_open_session_for_user(
    db: AsyncSession, tenant_id: str, user_id: str
) -> m.PosSession | None:
    return (
        await db.execute(
            select(m.PosSession).where(
                m.PosSession.tenant_id == tenant_id,
                m.PosSession.user_id == user_id,
                m.PosSession.status == "open",
            )
        )
    ).scalar_one_or_none()


async def require_open_session(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    session_id: str | None = None,
) -> m.PosSession:
    if session_id:
        session = await get_session(db, tenant_id, session_id)
        if session.status != "open":
            raise HTTPException(status_code=409, detail="POS session is not open")
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="POS session belongs to another cashier")
        return session

    session = await get_open_session_for_user(db, tenant_id, user_id)
    if not session:
        raise HTTPException(status_code=409, detail="Open a POS shift before recording sales")
    return session


async def open_session(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    store_id: str | None,
    opening_cash: float,
) -> m.PosSession:
    existing = await get_open_session_for_user(db, tenant_id, user_id)
    if existing:
        raise HTTPException(status_code=409, detail="Cashier already has an open POS shift")

    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(m.Store.id == store_id, m.Store.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")

    cash = round(float(opening_cash or 0), 2)
    if cash < 0:
        raise HTTPException(status_code=400, detail="opening_cash must be >= 0")

    session = m.PosSession(
        tenant_id=tenant_id,
        store_id=store_id,
        user_id=user_id,
        session_number=await next_session_number(db, tenant_id),
        status="open",
        opening_cash=cash,
        expected_cash=cash,
        cash_sales=0,
        card_sales=0,
        other_sales=0,
        total_sales=0,
        sale_count=0,
        opened_at=datetime.utcnow(),
    )
    db.add(session)
    await db.flush()
    return session


def resolve_sale_payments(
    *,
    total: float,
    payment_method: str | None,
    payments: list[dict] | None,
) -> list[dict]:
    """Normalize single or split tenders; amounts must sum to sale total."""
    sale_total = round(float(total or 0), 2)
    if sale_total < 0:
        raise HTTPException(status_code=400, detail="Sale total cannot be negative")

    if payments:
        if len(payments) < 1:
            raise HTTPException(status_code=400, detail="payments must include at least one tender")
        normalized: list[dict] = []
        for raw in payments:
            method = normalize_payment_method(raw.get("payment_method"))
            amount = round(float(raw.get("amount") or 0), 2)
            if amount <= 0:
                raise HTTPException(status_code=400, detail="Each payment amount must be > 0")
            normalized.append(
                {
                    "payment_method": method,
                    "amount": amount,
                    "reference": (raw.get("reference") or None),
                    "liquid_account_id": raw.get("liquid_account_id") or None,
                }
            )
        paid = round(sum(p["amount"] for p in normalized), 2)
        if abs(paid - sale_total) > 0.01:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "PAYMENT_TOTAL_MISMATCH",
                    "message": (
                        f"Payment tenders must sum to sale total "
                        f"(paid {paid:.2f}, due {sale_total:.2f})"
                    ),
                    "payments_total": paid,
                    "sale_total": sale_total,
                },
            )
        return normalized

    method = normalize_payment_method(payment_method)
    return [
        {
            "payment_method": method,
            "amount": sale_total,
            "reference": None,
            "liquid_account_id": None,
        }
    ]


def primary_payment_method(payments: list[dict]) -> str:
    """Single method, or 'split' when multiple tenders."""
    if len(payments) == 1:
        return payments[0]["payment_method"]
    return "split"


def credit_portion(payments: list[dict]) -> float:
    return round(
        sum(p["amount"] for p in payments if p["payment_method"] == "credit"),
        2,
    )


def has_cash_tender(payments: list[dict]) -> bool:
    return any(p["payment_method"] == "cash" for p in payments)


async def apply_sale_to_session(
    session: m.PosSession,
    *,
    total: float,
    payment_method: str,
    payments: list[dict] | None = None,
) -> None:
    amount = round(float(total or 0), 2)
    tenders = payments or [
        {"payment_method": normalize_payment_method(payment_method), "amount": amount}
    ]
    session.total_sales = round(float(session.total_sales or 0) + amount, 2)
    session.sale_count = int(session.sale_count or 0) + 1
    for tender in tenders:
        method = normalize_payment_method(tender.get("payment_method"))
        part = round(float(tender.get("amount") or 0), 2)
        if method == "cash":
            session.cash_sales = round(float(session.cash_sales or 0) + part, 2)
        elif method == "card":
            session.card_sales = round(float(session.card_sales or 0) + part, 2)
        else:
            session.other_sales = round(float(session.other_sales or 0) + part, 2)
    session.expected_cash = compute_expected_cash(session.opening_cash, session.cash_sales)


async def record_pos_payments(
    db: AsyncSession,
    *,
    tenant_id: str,
    sale_id: str,
    payments: list[dict],
) -> list[m.PosPayment]:
    rows: list[m.PosPayment] = []
    for tender in payments:
        row = m.PosPayment(
            tenant_id=tenant_id,
            sale_id=sale_id,
            payment_method=tender["payment_method"],
            amount=tender["amount"],
            reference=tender.get("reference"),
            liquid_account_id=tender.get("liquid_account_id"),
        )
        db.add(row)
        rows.append(row)
    await db.flush()
    return rows


def serialize_payment(row: m.PosPayment) -> dict:
    return {
        "id": row.id,
        "sale_id": row.sale_id,
        "payment_method": row.payment_method,
        "amount": float(row.amount or 0),
        "reference": row.reference,
        "liquid_account_id": row.liquid_account_id,
        "created_at": row.created_at,
    }


async def close_session(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    session_id: str,
    actual_cash: float,
    notes: str | None = None,
) -> m.PosSession:
    session = await get_session(db, tenant_id, session_id)
    if session.status != "open":
        raise HTTPException(status_code=409, detail="POS session is already closed")

    expected = compute_expected_cash(session.opening_cash, session.cash_sales)
    actual = round(float(actual_cash), 2)
    variance = compute_variance(actual, expected)

    session.expected_cash = expected
    session.actual_cash = actual
    session.variance = variance
    session.notes = notes
    session.status = "closed"
    session.closed_at = datetime.utcnow()

    if abs(variance) >= 0.01:
        from app.notifications import create_notification

        await create_notification(
            db,
            tenant_id=tenant_id,
            user_id=session.user_id,
            category="shift_variance",
            title="Shift Variance",
            message=(
                f"Session {session.session_number} cash variance: {variance:.2f} "
                f"(expected {expected:.2f}, actual {actual:.2f})"
            ),
            entity_type="pos_session",
            entity_id=session.id,
        )
    await db.flush()
    return session


async def drawer_summary(session: m.PosSession) -> dict:
    expected = compute_expected_cash(session.opening_cash, session.cash_sales)
    return {
        "session_id": session.id,
        "session_number": session.session_number,
        "status": session.status,
        "opening_cash": float(session.opening_cash or 0),
        "cash_sales": float(session.cash_sales or 0),
        "card_sales": float(session.card_sales or 0),
        "other_sales": float(session.other_sales or 0),
        "total_sales": float(session.total_sales or 0),
        "sale_count": int(session.sale_count or 0),
        "expected_cash": expected,
        "actual_cash": float(session.actual_cash) if session.actual_cash is not None else None,
        "variance": float(session.variance) if session.variance is not None else None,
    }


async def serialize_session(db: AsyncSession, session: m.PosSession) -> dict:
    drawer = await drawer_summary(session)
    store_name = None
    store_address = None
    if session.store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.id == session.store_id,
                    m.Store.tenant_id == session.tenant_id,
                )
            )
        ).scalar_one_or_none()
        if store:
            store_name = store.name
            store_address = store.address
    return {
        **drawer,
        "store_id": session.store_id,
        "store_name": store_name,
        "store_address": store_address,
        "user_id": session.user_id,
        "notes": session.notes,
        "opened_at": session.opened_at,
        "closed_at": session.closed_at,
    }


async def shift_report(db: AsyncSession, session: m.PosSession) -> dict:
    """Shift sales summary with discounts, returns, and payment breakdown (BR-8.2)."""
    sales = (
        await db.execute(
            select(m.Transaction)
            .where(
                m.Transaction.tenant_id == session.tenant_id,
                m.Transaction.session_id == session.id,
                m.Transaction.tx_type == "pos_sale",
            )
            .order_by(m.Transaction.created_at.asc())
        )
    ).scalars().all()

    sale_rows: list[dict] = []
    subtotal_sum = 0.0
    tax_sum = 0.0
    discount_sum = 0.0
    net_sum = 0.0
    for s in sales:
        payload = s.payload or {}
        cart_disc = float(payload.get("discount_amount") or 0)
        line_disc = float(payload.get("line_discounts") or 0)
        disc = round(cart_disc + line_disc, 2)
        subtotal = float(s.subtotal or 0)
        tax = float(s.tax or 0)
        total = float(s.total or 0)
        subtotal_sum += subtotal
        tax_sum += tax
        discount_sum += disc
        net_sum += total
        sale_rows.append(
            {
                "id": s.id,
                "reference": s.reference,
                "total": total,
                "tax": tax,
                "subtotal": subtotal,
                "status": s.status,
                "payment_method": payload.get("payment_method", "cash"),
                "payments": payload.get("payments") or [],
                "customer_name": payload.get("customer_name"),
                "discount_amount": cart_disc,
                "line_discounts": line_disc,
                "discounts": disc,
                "created_at": s.created_at,
            }
        )

    window_end = session.closed_at or datetime.utcnow()
    returns_raw = (
        await db.execute(
            select(m.SalesReturn)
            .where(
                m.SalesReturn.tenant_id == session.tenant_id,
                m.SalesReturn.created_at >= session.opened_at,
                m.SalesReturn.created_at <= window_end,
                m.SalesReturn.status != "cancelled",
            )
            .order_by(m.SalesReturn.created_at.asc())
        )
    ).scalars().all()

    return_rows: list[dict] = []
    return_total = 0.0
    for ret in returns_raw:
        include = ret.created_by == session.user_id
        if not include and session.store_id:
            inv = await db.get(m.SalesInvoice, ret.sales_invoice_id)
            include = bool(
                inv
                and inv.tenant_id == session.tenant_id
                and inv.store_id == session.store_id
            )
        if not include:
            continue
        amount = float(ret.total_amount or 0)
        return_total += amount
        return_rows.append(
            {
                "id": ret.id,
                "return_number": ret.return_number,
                "credit_note_number": ret.credit_note_number,
                "status": ret.status,
                "reason": ret.reason,
                "total_amount": amount,
                "sales_invoice_id": ret.sales_invoice_id,
                "posted_at": ret.posted_at,
                "created_at": ret.created_at,
            }
        )

    summary = {
        "sale_count": len(sale_rows),
        "subtotal": round(subtotal_sum, 2),
        "tax": round(tax_sum, 2),
        "discounts": round(discount_sum, 2),
        "net_sales": round(net_sum, 2),
        "return_count": len(return_rows),
        "return_total": round(return_total, 2),
        "net_after_returns": round(net_sum - return_total, 2),
    }

    return {
        "session": await serialize_session(db, session),
        "summary": summary,
        "sales": sale_rows,
        "returns": return_rows,
        "payment_breakdown": {
            "cash": float(session.cash_sales or 0),
            "card": float(session.card_sales or 0),
            "other": float(session.other_sales or 0),
            "total": float(session.total_sales or 0),
        },
    }
