"""Cash & bank account create + transfers / deposits / withdrawals (BR-10.3)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.accounting import ensure_default_accounts, get_account_by_code, post_journal_entry
from app.doc_numbers import next_cash_transfer_number

TRANSFER_KINDS = frozenset({"transfer", "deposit", "withdrawal"})
ACCOUNT_TYPES = frozenset({"asset", "liability", "equity", "income", "expense"})
LIQUID_KINDS = frozenset({"cash", "bank"})


def _is_liquid(account: m.Account) -> bool:
    return bool(account.is_cash_account or account.is_bank_account)


def serialize_account(account: m.Account) -> dict:
    from app.accounting import DEFAULT_ACCOUNTS

    system_codes = {c[0] for c in DEFAULT_ACCOUNTS}
    return {
        "id": account.id,
        "code": account.code,
        "name": account.name,
        "account_type": account.account_type,
        "balance": float(account.balance or 0),
        "opening_balance": float(getattr(account, "opening_balance", 0) or 0),
        "is_system": account.code in system_codes,
        "is_active": bool(getattr(account, "is_active", True)),
        "is_cash_account": bool(account.is_cash_account),
        "is_bank_account": bool(account.is_bank_account),
        "bank_name": account.bank_name,
        "account_number": account.account_number,
        "bank_branch": getattr(account, "bank_branch", None),
    }


def serialize_transfer(row: m.CashTransfer, *, accounts: dict[str, m.Account] | None = None) -> dict:
    accounts = accounts or {}
    from_acc = accounts.get(row.from_account_id) if row.from_account_id else None
    to_acc = accounts.get(row.to_account_id) if row.to_account_id else None
    return {
        "id": row.id,
        "kind": row.kind,
        "from_account_id": row.from_account_id,
        "to_account_id": row.to_account_id,
        "from_account": serialize_account(from_acc) if from_acc else None,
        "to_account": serialize_account(to_acc) if to_acc else None,
        "amount": float(row.amount),
        "reference": row.reference,
        "notes": row.notes,
        "journal_entry_id": row.journal_entry_id,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


async def get_account(db: AsyncSession, tenant_id: str, account_id: str) -> m.Account:
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


async def update_account(
    db: AsyncSession,
    *,
    tenant_id: str,
    account_id: str,
    name: str | None = None,
    bank_name: str | None = None,
    account_number: str | None = None,
    bank_branch: str | None = None,
    is_active: bool | None = None,
) -> m.Account:
    row = await get_account(db, tenant_id, account_id)
    if name is not None:
        name_key = name.strip()
        if not name_key:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        row.name = name_key
    if bank_name is not None:
        row.bank_name = bank_name.strip() or None
    if account_number is not None:
        row.account_number = account_number.strip() or None
    if bank_branch is not None:
        row.bank_branch = bank_branch.strip() or None
    if is_active is not None:
        row.is_active = bool(is_active)
    if row.is_bank_account and not row.bank_name:
        raise HTTPException(status_code=400, detail="bank_name is required for bank accounts")
    await db.flush()
    return row


async def create_account(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    account_type: str = "asset",
    liquid_kind: str | None = None,
    bank_name: str | None = None,
    account_number: str | None = None,
    bank_branch: str | None = None,
) -> m.Account:
    await ensure_default_accounts(db, tenant_id)
    code_key = (code or "").strip()
    name_key = (name or "").strip()
    if not code_key or not name_key:
        raise HTTPException(status_code=400, detail="code and name are required")
    atype = (account_type or "asset").strip().lower()
    if atype not in ACCOUNT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"account_type must be one of: {', '.join(sorted(ACCOUNT_TYPES))}",
        )
    kind = (liquid_kind or "").strip().lower() or None
    if kind and kind not in LIQUID_KINDS:
        raise HTTPException(status_code=422, detail="liquid_kind must be cash or bank")
    if kind:
        atype = "asset"
    exists = (
        await db.execute(
            select(m.Account).where(
                m.Account.tenant_id == tenant_id,
                m.Account.code == code_key,
            )
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Account code already exists")

    row = m.Account(
        tenant_id=tenant_id,
        code=code_key,
        name=name_key,
        account_type=atype,
        balance=0,
        is_cash_account=kind == "cash",
        is_bank_account=kind == "bank",
        bank_name=(bank_name or "").strip() or None,
        account_number=(account_number or "").strip() or None,
        bank_branch=(bank_branch or "").strip() or None,
    )
    if kind == "bank" and not row.bank_name:
        raise HTTPException(status_code=400, detail="bank_name is required for bank accounts")
    db.add(row)
    await db.flush()
    return row


async def list_transfers(db: AsyncSession, tenant_id: str, *, limit: int = 100) -> list[m.CashTransfer]:
    return list(
        (
            await db.execute(
                select(m.CashTransfer)
                .where(m.CashTransfer.tenant_id == tenant_id)
                .order_by(m.CashTransfer.created_at.desc())
                .limit(max(1, min(limit, 500)))
            )
        ).scalars().all()
    )


async def get_transfer(db: AsyncSession, tenant_id: str, transfer_id: str) -> m.CashTransfer:
    row = (
        await db.execute(
            select(m.CashTransfer).where(
                m.CashTransfer.id == transfer_id,
                m.CashTransfer.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return row


async def create_transfer(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    kind: str = "transfer",
    from_account_id: str | None = None,
    to_account_id: str | None = None,
    amount: float,
    reference: str | None = None,
    notes: str | None = None,
) -> m.CashTransfer:
    await ensure_default_accounts(db, tenant_id)
    kind_key = (kind or "transfer").strip().lower()
    if kind_key not in TRANSFER_KINDS:
        raise HTTPException(
            status_code=422,
            detail=f"kind must be one of: {', '.join(sorted(TRANSFER_KINDS))}",
        )
    amt = round(float(amount or 0), 2)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="amount must be greater than zero")

    equity = await get_account_by_code(db, tenant_id, "3000")

    if kind_key == "transfer":
        if not from_account_id or not to_account_id:
            raise HTTPException(status_code=400, detail="from_account_id and to_account_id are required")
        if from_account_id == to_account_id:
            raise HTTPException(status_code=400, detail="Cannot transfer to the same account")
        src = await get_account(db, tenant_id, from_account_id)
        dst = await get_account(db, tenant_id, to_account_id)
        from app.accounting import assert_account_active

        assert_account_active(src)
        assert_account_active(dst)
        if not _is_liquid(src) or not _is_liquid(dst):
            raise HTTPException(status_code=400, detail="Transfers require cash/bank liquid accounts")
        debit_id, credit_id = dst.id, src.id
        description = f"Transfer {src.code} → {dst.code}"
    elif kind_key == "deposit":
        if not to_account_id:
            raise HTTPException(status_code=400, detail="to_account_id is required for deposit")
        dst = await get_account(db, tenant_id, to_account_id)
        from app.accounting import assert_account_active

        assert_account_active(dst)
        if not _is_liquid(dst):
            raise HTTPException(status_code=400, detail="Deposit destination must be a cash/bank account")
        src = equity
        from_account_id = equity.id
        debit_id, credit_id = dst.id, equity.id
        description = f"Deposit to {dst.code}"
    else:  # withdrawal
        if not from_account_id:
            raise HTTPException(status_code=400, detail="from_account_id is required for withdrawal")
        src = await get_account(db, tenant_id, from_account_id)
        from app.accounting import assert_account_active

        assert_account_active(src)
        if not _is_liquid(src):
            raise HTTPException(status_code=400, detail="Withdrawal source must be a cash/bank account")
        dst = equity
        to_account_id = equity.id
        debit_id, credit_id = equity.id, src.id
        description = f"Withdrawal from {src.code}"

    if notes:
        description = f"{description}: {notes.strip()[:120]}"

    ref = (reference or "").strip() or None
    if ref is None:
        ref = await next_cash_transfer_number(db, tenant_id)

    transfer = m.CashTransfer(
        tenant_id=tenant_id,
        kind=kind_key,
        from_account_id=from_account_id,
        to_account_id=to_account_id,
        amount=amt,
        reference=ref,
        notes=(notes or "").strip() or None,
        created_by=user_id,
        created_at=datetime.utcnow(),
    )
    db.add(transfer)
    await db.flush()

    entry = await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description,
        reference=transfer.reference,
        source_type="cash_transfer",
        source_id=transfer.id,
        lines=[
            {"account_id": debit_id, "debit": amt, "credit": 0, "description": description},
            {"account_id": credit_id, "debit": 0, "credit": amt, "description": description},
        ],
    )
    transfer.journal_entry_id = entry.id
    await db.flush()
    return transfer


async def accounts_map_for_transfers(
    db: AsyncSession, tenant_id: str, rows: list[m.CashTransfer]
) -> dict[str, m.Account]:
    ids = {r.from_account_id for r in rows if r.from_account_id} | {
        r.to_account_id for r in rows if r.to_account_id
    }
    if not ids:
        return {}
    found = (
        await db.execute(
            select(m.Account).where(
                m.Account.tenant_id == tenant_id,
                m.Account.id.in_(ids),
            )
        )
    ).scalars().all()
    return {a.id: a for a in found}
