"""Other operating income (not sales): CRUD + cash/bank journal. Payment info only."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.expenses import normalize_expense_payment_method


async def list_incomes(db: AsyncSession, tenant_id: str) -> list[m.OtherIncome]:
    return (
        (
            await db.execute(
                select(m.OtherIncome)
                .where(m.OtherIncome.tenant_id == tenant_id)
                .order_by(m.OtherIncome.income_date.desc())
            )
        )
        .scalars()
        .all()
    )


def serialize_income(row: m.OtherIncome) -> dict:
    return {
        "id": row.id,
        "description": row.description,
        "amount": money_json(row.amount),
        "income_date": row.income_date,
        "payment_method": row.payment_method,
        "liquid_account_id": row.liquid_account_id,
        "payer": row.payer,
        "reference": row.reference,
        "status": row.status,
        "journal_entry_id": row.journal_entry_id,
        "created_at": row.created_at,
    }


async def create_income(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    payload: dict,
) -> m.OtherIncome:
    amount = money_json(payload.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Income amount must be greater than zero")
    method = normalize_expense_payment_method(payload.get("payment_method"), default="cash")
    row = m.OtherIncome(
        tenant_id=tenant_id,
        description=require_honest_narrative(
            payload.get("description"), label="income description", max_length=500
        ),
        amount=amount,
        income_date=payload.get("income_date") or datetime.utcnow(),
        payment_method=method,
        liquid_account_id=payload.get("liquid_account_id"),
        payer=optional_honest_narrative(payload.get("payer"), label="payer", max_length=150),
        reference=optional_honest_narrative(payload.get("reference"), label="income reference", max_length=100),
        status="posted",
        created_by=user_id,
    )
    db.add(row)
    await db.flush()

    from app.accounting import ensure_default_accounts, post_journal_entry, resolve_settlement_gl

    await ensure_default_accounts(db, tenant_id)

    debit_code, _ = await resolve_settlement_gl(
        db,
        tenant_id,
        method,
        liquid_account_id=row.liquid_account_id,
        outflow=False,
    )
    je = await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Other income {row.description[:80]}",
        source_type="other_income",
        source_id=row.id,
        lines=[
            {"account_code": debit_code, "debit": amount, "credit": 0, "description": row.description},
            {"account_code": "4400", "debit": 0, "credit": amount, "description": row.description},
        ],
    )
    row.journal_entry_id = je.id
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="other_income_posted",
            entity="other_income",
            entity_id=row.id,
            details={"amount": amount, "journal_entry_id": je.id},
        )
    )
    await db.flush()
    return row
