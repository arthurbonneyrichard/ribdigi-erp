"""POS shift / session management and cash reconciliation."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.doc_numbers import (  # re-exported for API callers
    next_pos_sale_number,
    next_pos_session_number,
    resolve_pos_company_id,
)
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

CASH_MOVEMENT_TYPES = frozenset({"cash_in", "cash_out"})
SESSION_SUPERVISOR_ROLES = frozenset(
    {"company_admin", "super_admin", "store_manager"}
)


def compute_expected_cash(
    opening_cash: float,
    cash_sales: float,
    cash_in: float = 0,
    cash_out: float = 0,
) -> float:
    return money_json(
        round(
            money_json(opening_cash or 0)
            + money_json(cash_sales or 0)
            + money_json(cash_in or 0)
            - money_json(cash_out or 0),
            2,
        )
    )


def expected_cash_for_session(session: m.PosSession) -> float:
    return compute_expected_cash(
        session.opening_cash,
        session.cash_sales,
        getattr(session, "cash_in", 0) or 0,
        getattr(session, "cash_out", 0) or 0,
    )


def compute_variance(actual_cash: float, expected_cash: float) -> float:
    return money_json(round(money_json(actual_cash) - money_json(expected_cash), 2))


PAYMENT_METHODS = frozenset({"cash", "card", "wallet", "credit", "other", "gift_card", "loyalty"})
PAYMENT_METHOD_ALIASES = {
    "digital_wallet": "wallet",
    "mobile_money": "wallet",
    "momo": "wallet",
    "mobilemoney": "wallet",
}


def coerce_payment_method_value(value: object) -> object:
    """Pydantic BeforeValidator: map wallet aliases; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    text = value.strip().lower().replace("-", "_").replace(" ", "_")
    if not text:
        return ""
    return PAYMENT_METHOD_ALIASES.get(text, text)


def normalize_payment_method(method: str | None, *, strict: bool = True) -> str:
    # Defense in depth: PosSaleCreate / PosPaymentLine Literals reject blank/
    # unknown (after alias coerce) with 422. Unknown used to become silent "other".
    if method is not None and not str(method).strip():
        if strict:
            raise HTTPException(
                status_code=400,
                detail=f"payment_method must be one of: {', '.join(sorted(PAYMENT_METHODS))}",
            )
        method = None
    value = (method or "cash").strip().lower().replace("-", "_").replace(" ", "_")
    value = PAYMENT_METHOD_ALIASES.get(value, value)
    if value in PAYMENT_METHODS:
        return value
    if strict:
        raise HTTPException(
            status_code=400,
            detail=f"payment_method must be one of: {', '.join(sorted(PAYMENT_METHODS))}",
        )
    return "other"


async def next_session_number(
    db: AsyncSession, tenant_id: str, *, company_id: str | None = None
) -> str:
    return await next_pos_session_number(db, tenant_id, company_id=company_id)


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
        from app import store_access as store_access_svc

        await store_access_svc.assert_store_access(
            db, tenant_id=tenant_id, user_id=user_id, store_id=session.store_id
        )
        return session

    session = await get_open_session_for_user(db, tenant_id, user_id)
    if not session:
        raise HTTPException(status_code=409, detail="Open a POS shift before recording sales")
    from app import store_access as store_access_svc

    await store_access_svc.assert_store_access(
        db, tenant_id=tenant_id, user_id=user_id, store_id=session.store_id
    )
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
        from app import stores as stores_svc
        from app import store_access as store_access_svc

        store = await stores_svc.require_active_store(db, tenant_id, store_id)
        await store_access_svc.assert_store_access(
            db, tenant_id=tenant_id, user_id=user_id, store_id=store.id
        )

    cash = money_json(round(money_json(opening_cash or 0), 2))
    if cash < 0:
        raise HTTPException(status_code=400, detail="opening_cash must be >= 0")

    company_id = await resolve_pos_company_id(db, tenant_id, store_id)
    session = m.PosSession(
        tenant_id=tenant_id,
        store_id=store_id,
        user_id=user_id,
        session_number=await next_session_number(db, tenant_id, company_id=company_id),
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
    sale_total = money_json(round(money_json(total or 0), 2))
    if sale_total < 0:
        raise HTTPException(status_code=400, detail="Sale total cannot be negative")

    if payments:
        if len(payments) < 1:
            raise HTTPException(status_code=400, detail="payments must include at least one tender")
        normalized: list[dict] = []
        for raw in payments:
            method = normalize_payment_method(raw.get("payment_method"))
            amount = money_json(round(money_json(raw.get("amount") or 0), 2))
            if amount <= 0:
                raise HTTPException(status_code=400, detail="Each payment amount must be > 0")
            normalized.append(
                {
                    "payment_method": method,
                    "amount": amount,
                    "reference": optional_honest_narrative(
                        raw.get("reference"), label="payment reference", max_length=100
                    ),
                    "liquid_account_id": raw.get("liquid_account_id") or None,
                }
            )
        paid = money_json(round(sum(p["amount"] for p in normalized), 2))
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
    return money_json(
        round(
            sum(p["amount"] for p in payments if p["payment_method"] == "credit"),
            2,
        )
    )


def collected_portion(payments: list[dict]) -> float:
    return money_json(
        round(
            sum(p["amount"] for p in payments if p["payment_method"] != "credit"),
            2,
        )
    )


def sale_settlement(
    *,
    total: float,
    payments: list[dict] | None = None,
    payment_method: str | None = None,
) -> dict:
    """Sale total vs cash/card collected vs on-account remainder (not a second ledger)."""
    sale_total = money_json(round(money_json(total or 0), 2))
    tenders = list(payments or [])
    if not tenders:
        method = normalize_payment_method(payment_method, strict=False)
        tenders = [{"payment_method": method, "amount": sale_total}]
    credit = credit_portion(tenders)
    paid = money_json(round(max(sale_total - credit, 0), 2))
    if credit <= 1e-9:
        status = "paid"
    elif paid > 1e-9:
        status = "partially_paid"
    else:
        status = "unpaid"
    return {
        "paid_amount": paid,
        "credit_amount": money_json(credit),
        "balance_due": money_json(credit),
        "payment_status": status,
    }


def has_cash_tender(payments: list[dict]) -> bool:
    return any(p["payment_method"] == "cash" for p in payments)


async def apply_sale_to_session(
    session: m.PosSession,
    *,
    total: float,
    payment_method: str,
    payments: list[dict] | None = None,
) -> None:
    amount = money_json(round(money_json(total or 0), 2))
    tenders = payments or [
        {"payment_method": normalize_payment_method(payment_method), "amount": amount}
    ]
    session.total_sales = money_json(round(money_json(session.total_sales or 0) + amount, 2))
    session.sale_count = int(session.sale_count or 0) + 1
    for tender in tenders:
        method = normalize_payment_method(tender.get("payment_method"))
        part = money_json(round(money_json(tender.get("amount") or 0), 2))
        if method == "cash":
            session.cash_sales = money_json(round(money_json(session.cash_sales or 0) + part, 2))
        elif method == "card":
            session.card_sales = money_json(round(money_json(session.card_sales or 0) + part, 2))
        else:
            session.other_sales = money_json(round(money_json(session.other_sales or 0) + part, 2))
    session.expected_cash = expected_cash_for_session(session)


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
        "amount": money_json(row.amount),
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
    # OpenAPI PosSessionCloseNotesValue → 422; service defense-in-depth → 400.
    notes_s = optional_honest_narrative(notes, label="close notes")
    session = await get_session(db, tenant_id, session_id)
    if session.status != "open":
        raise HTTPException(status_code=409, detail="POS session is already closed")

    expected = expected_cash_for_session(session)
    actual = money_json(round(money_json(actual_cash), 2))
    variance = compute_variance(actual, expected)

    session.expected_cash = expected
    session.actual_cash = actual
    session.variance = variance
    session.notes = notes_s
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
    expected = expected_cash_for_session(session)
    cash_in = money_json(getattr(session, "cash_in", 0) or 0)
    cash_out = money_json(getattr(session, "cash_out", 0) or 0)
    return {
        "session_id": session.id,
        "session_number": session.session_number,
        "status": session.status,
        "opening_cash": money_json(session.opening_cash),
        "cash_sales": money_json(session.cash_sales),
        "cash_in": cash_in,
        "cash_out": cash_out,
        "card_sales": money_json(session.card_sales),
        "other_sales": money_json(session.other_sales),
        "total_sales": money_json(session.total_sales),
        "sale_count": int(session.sale_count or 0),
        "expected_cash": expected,
        "actual_cash": money_json(session.actual_cash) if session.actual_cash is not None else None,
        "variance": money_json(session.variance) if session.variance is not None else None,
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
    cashier = (
        await db.execute(
            select(m.User).where(
                m.User.id == session.user_id,
                m.User.tenant_id == session.tenant_id,
            )
        )
    ).scalar_one_or_none()
    return {
        **drawer,
        "store_id": session.store_id,
        "store_name": store_name,
        "store_address": store_address,
        "user_id": session.user_id,
        "cashier_id": session.user_id,
        "cashier_name": cashier.full_name if cashier else None,
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
        cart_disc = money_json(payload.get("discount_amount") or 0)
        line_disc = money_json(payload.get("line_discounts") or 0)
        disc = money_json(round(cart_disc + line_disc, 2))
        subtotal = money_json(s.subtotal or 0)
        tax = money_json(s.tax or 0)
        total = money_json(s.total or 0)
        subtotal_sum += subtotal
        tax_sum += tax
        discount_sum += disc
        net_sum += total
        settle = sale_settlement(
            total=total,
            payments=payload.get("payments") or None,
            payment_method=payload.get("payment_method"),
        )
        sale_rows.append(
            {
                "id": s.id,
                "reference": s.reference,
                "total": money_json(total),
                "tax": money_json(tax),
                "subtotal": money_json(subtotal),
                "status": s.status,
                "payment_method": payload.get("payment_method", "cash"),
                "payments": payload.get("payments") or [],
                "customer_name": payload.get("customer_name"),
                "cashier_id": session.user_id,
                "session_id": session.id,
                "discount_amount": money_json(cart_disc),
                "line_discounts": money_json(line_disc),
                "discounts": money_json(disc),
                "created_at": s.created_at,
                "paid_amount": settle["paid_amount"],
                "balance_due": settle["balance_due"],
                "payment_status": settle["payment_status"],
                "sales_invoice_id": payload.get("sales_invoice_id"),
                "invoice_number": payload.get("invoice_number"),
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
        amount = money_json(ret.total_amount or 0)
        return_total += amount
        return_rows.append(
            {
                "id": ret.id,
                "return_number": ret.return_number,
                "credit_note_number": ret.credit_note_number,
                "status": ret.status,
                "reason": ret.reason,
                "total_amount": money_json(amount),
                "sales_invoice_id": ret.sales_invoice_id,
                "posted_at": ret.posted_at,
                "created_at": ret.created_at,
            }
        )

    summary = {
        "sale_count": len(sale_rows),
        "subtotal": money_json(round(subtotal_sum, 2)),
        "tax": money_json(round(tax_sum, 2)),
        "discounts": money_json(round(discount_sum, 2)),
        "net_sales": money_json(round(net_sum, 2)),
        "return_count": len(return_rows),
        "return_total": money_json(round(return_total, 2)),
        "net_after_returns": money_json(round(net_sum - return_total, 2)),
    }

    movements = await list_cash_movements(db, session)
    return {
        "session": await serialize_session(db, session),
        "summary": summary,
        "sales": sale_rows,
        "returns": return_rows,
        "cash_movements": movements,
        "payment_breakdown": {
            "cash": money_json(session.cash_sales or 0),
            "card": money_json(session.card_sales or 0),
            "other": money_json(session.other_sales or 0),
            "cash_in": money_json(getattr(session, "cash_in", 0) or 0),
            "cash_out": money_json(getattr(session, "cash_out", 0) or 0),
            "total": money_json(session.total_sales or 0),
        },
    }


def serialize_cash_movement(row: m.PosCashMovement) -> dict:
    return {
        "id": row.id,
        "session_id": row.session_id,
        "store_id": row.store_id,
        "user_id": row.user_id,
        "movement_type": row.movement_type,
        "amount": money_json(row.amount),
        "reason": row.reason,
        "created_at": row.created_at,
    }


async def list_cash_movements(db: AsyncSession, session: m.PosSession) -> list[dict]:
    rows = (
        await db.execute(
            select(m.PosCashMovement)
            .where(
                m.PosCashMovement.tenant_id == session.tenant_id,
                m.PosCashMovement.session_id == session.id,
            )
            .order_by(m.PosCashMovement.created_at.asc())
        )
    ).scalars().all()
    return [serialize_cash_movement(r) for r in rows]


def assert_can_operate_session(session: m.PosSession, claims: dict) -> None:
    """Cashier may operate own shift; store managers/admins may operate assigned-store shifts."""
    if session.user_id == claims.get("sub"):
        return
    role = (claims.get("role") or "").strip().lower()
    if role in SESSION_SUPERVISOR_ROLES:
        return
    raise HTTPException(status_code=403, detail="Not your POS session")


async def record_cash_movement(
    db: AsyncSession,
    *,
    session: m.PosSession,
    user_id: str,
    movement_type: str,
    amount: float,
    reason: str,
) -> m.PosCashMovement:
    kind = (movement_type or "").strip().lower()
    if kind not in CASH_MOVEMENT_TYPES:
        raise HTTPException(status_code=400, detail="movement_type must be cash_in or cash_out")
    if session.status != "open":
        raise HTTPException(status_code=409, detail="POS session is not open")
    qty = money_json(round(money_json(amount), 2))
    if qty <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    reason_s = require_honest_narrative(reason, label="cash movement reason", max_length=200)

    row = m.PosCashMovement(
        tenant_id=session.tenant_id,
        session_id=session.id,
        store_id=session.store_id,
        user_id=user_id,
        movement_type=kind,
        amount=qty,
        reason=reason_s,
    )
    db.add(row)
    if kind == "cash_in":
        session.cash_in = money_json(round(money_json(getattr(session, "cash_in", 0) or 0) + qty, 2))
    else:
        session.cash_out = money_json(round(money_json(getattr(session, "cash_out", 0) or 0) + qty, 2))
    session.expected_cash = expected_cash_for_session(session)
    await db.flush()
    return row
