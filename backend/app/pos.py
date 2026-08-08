"""POS shift / session management and cash reconciliation."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m


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
    count = len(
        (
            await db.execute(select(m.PosSession.id).where(m.PosSession.tenant_id == tenant_id))
        ).scalars().all()
    )
    return f"POS-{datetime.utcnow():%Y%m%d}-{count + 1:04d}"


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


async def apply_sale_to_session(
    session: m.PosSession,
    *,
    total: float,
    payment_method: str,
) -> None:
    amount = round(float(total or 0), 2)
    method = normalize_payment_method(payment_method)
    session.total_sales = round(float(session.total_sales or 0) + amount, 2)
    session.sale_count = int(session.sale_count or 0) + 1
    if method == "cash":
        session.cash_sales = round(float(session.cash_sales or 0) + amount, 2)
    elif method == "card":
        session.card_sales = round(float(session.card_sales or 0) + amount, 2)
    else:
        session.other_sales = round(float(session.other_sales or 0) + amount, 2)
    session.expected_cash = compute_expected_cash(session.opening_cash, session.cash_sales)


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


async def serialize_session(session: m.PosSession) -> dict:
    drawer = await drawer_summary(session)
    return {
        **drawer,
        "store_id": session.store_id,
        "user_id": session.user_id,
        "notes": session.notes,
        "opened_at": session.opened_at,
        "closed_at": session.closed_at,
    }


async def shift_report(db: AsyncSession, session: m.PosSession) -> dict:
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
    return {
        "session": await serialize_session(session),
        "sales": [
            {
                "id": s.id,
                "reference": s.reference,
                "total": float(s.total or 0),
                "tax": float(s.tax or 0),
                "status": s.status,
                "payment_method": (s.payload or {}).get("payment_method", "cash"),
                "created_at": s.created_at,
            }
            for s in sales
        ],
        "payment_breakdown": {
            "cash": float(session.cash_sales or 0),
            "card": float(session.card_sales or 0),
            "other": float(session.other_sales or 0),
        },
    }
