"""COA opening balance entry (BR-10.1) — fiscal-year / go-live GL openings."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.accounting import (
    DEFAULT_ACCOUNTS,
    ensure_default_accounts,
    get_account_by_code,
    post_journal_entry,
)

DEBIT_TYPES = frozenset({"asset", "expense"})
CREDIT_TYPES = frozenset({"liability", "equity", "income"})
EQUITY_PLUG_CODE = "3000"


async def _resolve_account(
    db: AsyncSession, tenant_id: str, *, account_id: str | None, account_code: str | None
) -> m.Account:
    if account_id:
        row = (
            await db.execute(
                select(m.Account).where(
                    m.Account.id == account_id,
                    m.Account.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Account not found")
        return row
    if account_code:
        row = await get_account_by_code(db, tenant_id, account_code.strip())
        if not row:
            raise HTTPException(status_code=404, detail=f"Account not found: {account_code}")
        return row
    raise HTTPException(status_code=400, detail="Each line needs account_id or account_code")


async def existing_coa_opening(db: AsyncSession, tenant_id: str) -> m.JournalEntry | None:
    return (
        await db.execute(
            select(m.JournalEntry)
            .where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "coa_opening",
            )
            .order_by(m.JournalEntry.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def post_coa_opening_balances(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    lines: list[dict],
    reference: str | None = None,
    notes: str | None = None,
) -> dict:
    if not lines:
        raise HTTPException(status_code=400, detail="Opening balances require at least one line")

    await ensure_default_accounts(db, tenant_id)
    prior = await existing_coa_opening(db, tenant_id)
    if prior:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "COA_OPENING_EXISTS",
                "message": "COA opening balances already posted for this tenant",
                "journal_id": prior.id,
                "entry_number": prior.entry_number,
            },
        )

    entry_id = str(uuid.uuid4())
    ref_label = (reference or "").strip() or f"COA-OPEN-{datetime.utcnow():%Y%m%d}"
    journal_lines: list[dict] = []
    snapshots: list[dict] = []
    seen: set[str] = set()
    total_debit = 0.0
    total_credit = 0.0

    for raw in lines:
        account = await _resolve_account(
            db,
            tenant_id,
            account_id=raw.get("account_id"),
            account_code=raw.get("account_code"),
        )
        if account.id in seen:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate opening line for account {account.code}",
            )
        seen.add(account.id)
        amount = float(raw.get("amount") or 0)
        if amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be positive")

        atype = (account.account_type or "").lower()
        if atype in DEBIT_TYPES:
            debit, credit = amount, 0.0
            total_debit += amount
        elif atype in CREDIT_TYPES:
            debit, credit = 0.0, amount
            total_credit += amount
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported account_type for opening balance: {account.account_type}",
            )

        journal_lines.append(
            {
                "account_id": account.id,
                "debit": debit,
                "credit": credit,
                "description": f"Opening balance {account.code}",
            }
        )
        account.opening_balance = amount
        snapshots.append(
            {
                "account_id": account.id,
                "code": account.code,
                "name": account.name,
                "account_type": account.account_type,
                "amount": amount,
                "side": "debit" if debit else "credit",
            }
        )

    # Auto-plug residual to Owner's Equity (3000)
    residual = round(total_debit - total_credit, 2)
    plug_account = None
    if abs(residual) > 0.009:
        plug_account = await get_account_by_code(db, tenant_id, EQUITY_PLUG_CODE)
        if not plug_account:
            raise HTTPException(status_code=500, detail="Equity account 3000 missing")
        # Merge into existing equity line if present
        existing_plug = next(
            (jl for jl in journal_lines if jl["account_id"] == plug_account.id), None
        )
        if residual > 0:
            # Need more credit
            if existing_plug:
                existing_plug["credit"] = round(float(existing_plug["credit"]) + residual, 2)
            else:
                journal_lines.append(
                    {
                        "account_id": plug_account.id,
                        "debit": 0.0,
                        "credit": residual,
                        "description": "Opening balance plug (equity)",
                    }
                )
            plug_account.opening_balance = round(
                float(plug_account.opening_balance or 0) + residual, 2
            )
        else:
            need_debit = abs(residual)
            if existing_plug:
                # reduce credit or flip — simplest: add debit side
                if float(existing_plug["credit"]) >= need_debit:
                    existing_plug["credit"] = round(float(existing_plug["credit"]) - need_debit, 2)
                    if existing_plug["credit"] == 0 and existing_plug["debit"] == 0:
                        journal_lines.remove(existing_plug)
                else:
                    raise HTTPException(
                        status_code=400,
                        detail="Opening balances cannot be auto-balanced; check liability/equity vs asset totals",
                    )
            else:
                journal_lines.append(
                    {
                        "account_id": plug_account.id,
                        "debit": need_debit,
                        "credit": 0.0,
                        "description": "Opening balance plug (equity)",
                    }
                )
            plug_account.opening_balance = round(
                float(plug_account.opening_balance or 0) - need_debit, 2
            )

    if len(journal_lines) < 2:
        raise HTTPException(
            status_code=400,
            detail="Opening balances must produce at least two journal lines (add more accounts or a balancing plug)",
        )

    journal = await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=notes or f"COA opening balances {ref_label}",
        reference=ref_label,
        source_type="coa_opening",
        source_id=entry_id,
        lines=journal_lines,
    )

    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="coa_opening_posted",
            entity="coa_opening",
            entity_id=entry_id,
            details={
                "reference": ref_label,
                "line_count": len(snapshots),
                "journal_id": journal.id,
                "plugged_equity": plug_account is not None and abs(residual) > 0.009,
            },
        )
    )

    system_codes = {c[0] for c in DEFAULT_ACCOUNTS}
    return {
        "id": entry_id,
        "reference": ref_label,
        "journal_id": journal.id,
        "journal_number": journal.entry_number,
        "total_debit": float(journal.total_debit),
        "total_credit": float(journal.total_credit),
        "equity_plug_amount": residual if abs(residual) > 0.009 else 0.0,
        "lines": snapshots,
        "system_account_codes": sorted(system_codes),
    }


async def opening_status(db: AsyncSession, tenant_id: str) -> dict:
    await ensure_default_accounts(db, tenant_id)
    prior = await existing_coa_opening(db, tenant_id)
    return {
        "posted": prior is not None,
        "journal_id": prior.id if prior else None,
        "journal_number": prior.entry_number if prior else None,
        "reference": prior.reference if prior else None,
        "posted_at": prior.created_at if prior else None,
    }
