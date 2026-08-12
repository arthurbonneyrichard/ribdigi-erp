"""CSV export for POS sales register and session Z-reports (Stage 142)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import pos as pos_svc
from app.session_passkey_doc_export import _cell

POS_SALE_EXPORT_COLUMNS = [
    "id",
    "reference",
    "session_id",
    "session_number",
    "store_id",
    "party_id",
    "subtotal",
    "tax",
    "total",
    "status",
    "payment_method",
    "cash_amount",
    "card_amount",
    "other_amount",
    "credit_amount",
    "created_at",
]

Z_REPORT_EXPORT_COLUMNS = [
    "row_type",
    "session_id",
    "session_number",
    "status",
    "store_id",
    "user_id",
    "opening_cash",
    "cash_sales",
    "card_sales",
    "other_sales",
    "total_sales",
    "sale_count",
    "expected_cash",
    "actual_cash",
    "variance",
    "opened_at",
    "closed_at",
    "sale_id",
    "sale_reference",
    "sale_total",
    "sale_tax",
    "sale_status",
    "sale_payment_method",
    "sale_created_at",
]


def _payment_amounts(payload: dict | None) -> dict:
    payload = payload or {}
    method = (payload.get("payment_method") or "cash").strip().lower()
    payments = payload.get("payments") or []
    cash = card = other = credit = 0.0
    if payments:
        for p in payments:
            amt = float(p.get("amount") or 0)
            mth = (p.get("method") or p.get("payment_method") or "").strip().lower()
            if mth in {"cash"}:
                cash += amt
            elif mth in {"card", "debit", "credit_card"}:
                card += amt
            elif mth in {"credit", "on_account"}:
                credit += amt
            else:
                other += amt
    else:
        total = float(payload.get("total") or 0)
        if method == "cash":
            cash = total
        elif method in {"card", "debit", "credit_card"}:
            card = total
        elif method in {"credit", "on_account"}:
            credit = total
        else:
            other = total
    return {
        "cash_amount": round(cash, 2),
        "card_amount": round(card, 2),
        "other_amount": round(other, 2),
        "credit_amount": round(credit, 2),
        "payment_method": method,
    }


async def list_pos_sales(
    db: AsyncSession,
    *,
    tenant_id: str,
    session_id: str | None = None,
    store_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 500,
) -> list[tuple[m.Transaction, m.PosSession | None]]:
    """Stage 142 S1 — tenant POS sales register (header rows)."""
    stmt = (
        select(m.Transaction, m.PosSession)
        .outerjoin(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
        )
        .order_by(m.Transaction.created_at.desc())
        .limit(min(max(limit, 1), 500))
    )
    if session_id:
        stmt = stmt.where(m.Transaction.session_id == session_id.strip())
    if store_id:
        stmt = stmt.where(m.PosSession.store_id == store_id.strip())
    if from_date:
        stmt = stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.Transaction.created_at <= to_date)
    return list((await db.execute(stmt)).all())


def serialize_pos_sale(tx: m.Transaction, session: m.PosSession | None) -> dict:
    amounts = _payment_amounts(tx.payload if isinstance(tx.payload, dict) else {})
    # Prefer amounts derived from payload payments; fall back to total for single tender
    if (
        amounts["cash_amount"] == 0
        and amounts["card_amount"] == 0
        and amounts["other_amount"] == 0
        and amounts["credit_amount"] == 0
    ):
        total = float(tx.total or 0)
        method = amounts["payment_method"]
        if method == "cash":
            amounts["cash_amount"] = total
        elif method in {"card", "debit", "credit_card"}:
            amounts["card_amount"] = total
        elif method in {"credit", "on_account"}:
            amounts["credit_amount"] = total
        else:
            amounts["other_amount"] = total
    return {
        "id": tx.id,
        "reference": tx.reference,
        "session_id": tx.session_id,
        "session_number": session.session_number if session else "",
        "store_id": session.store_id if session else "",
        "party_id": tx.party_id,
        "subtotal": float(tx.subtotal or 0),
        "tax": float(tx.tax or 0),
        "total": float(tx.total or 0),
        "status": tx.status,
        "payment_method": amounts["payment_method"],
        "cash_amount": amounts["cash_amount"],
        "card_amount": amounts["card_amount"],
        "other_amount": amounts["other_amount"],
        "credit_amount": amounts["credit_amount"],
        "created_at": tx.created_at,
    }


async def export_pos_sales_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    session_id: str | None = None,
    store_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> str:
    rows = await list_pos_sales(
        db,
        tenant_id=tenant_id,
        session_id=session_id,
        store_id=store_id,
        from_date=from_date,
        to_date=to_date,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=POS_SALE_EXPORT_COLUMNS)
    writer.writeheader()
    for tx, session in rows:
        data = serialize_pos_sale(tx, session)
        writer.writerow({k: _cell(data.get(k)) for k in POS_SALE_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_session_z_report_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    session_id: str,
) -> str:
    """Stage 142 Z1 — session summary row + sale detail rows."""
    session = await pos_svc.get_session(db, tenant_id, session_id)
    report = await pos_svc.shift_report(db, session)
    sess = report.get("session") or {}
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=Z_REPORT_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "row_type": "session",
            "session_id": _cell(sess.get("session_id")),
            "session_number": _cell(sess.get("session_number")),
            "status": _cell(sess.get("status")),
            "store_id": _cell(sess.get("store_id")),
            "user_id": _cell(sess.get("user_id")),
            "opening_cash": _cell(sess.get("opening_cash")),
            "cash_sales": _cell(sess.get("cash_sales")),
            "card_sales": _cell(sess.get("card_sales")),
            "other_sales": _cell(sess.get("other_sales")),
            "total_sales": _cell(sess.get("total_sales")),
            "sale_count": _cell(sess.get("sale_count")),
            "expected_cash": _cell(sess.get("expected_cash")),
            "actual_cash": _cell(sess.get("actual_cash")),
            "variance": _cell(sess.get("variance")),
            "opened_at": _cell(sess.get("opened_at")),
            "closed_at": _cell(sess.get("closed_at")),
            "sale_id": "",
            "sale_reference": "",
            "sale_total": "",
            "sale_tax": "",
            "sale_status": "",
            "sale_payment_method": "",
            "sale_created_at": "",
        }
    )
    for sale in report.get("sales") or []:
        writer.writerow(
            {
                "row_type": "sale",
                "session_id": _cell(sess.get("session_id")),
                "session_number": _cell(sess.get("session_number")),
                "status": _cell(sess.get("status")),
                "store_id": _cell(sess.get("store_id")),
                "user_id": _cell(sess.get("user_id")),
                "opening_cash": "",
                "cash_sales": "",
                "card_sales": "",
                "other_sales": "",
                "total_sales": "",
                "sale_count": "",
                "expected_cash": "",
                "actual_cash": "",
                "variance": "",
                "opened_at": "",
                "closed_at": "",
                "sale_id": _cell(sale.get("id")),
                "sale_reference": _cell(sale.get("reference")),
                "sale_total": _cell(sale.get("total")),
                "sale_tax": _cell(sale.get("tax")),
                "sale_status": _cell(sale.get("status")),
                "sale_payment_method": _cell(sale.get("payment_method")),
                "sale_created_at": _cell(sale.get("created_at")),
            }
        )
    return buf.getvalue()
