"""Double-entry accounting helpers and auto-posting."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

DEFAULT_ACCOUNTS = [
    ("1000", "Cash", "asset", True, False),
    ("1010", "Bank", "asset", False, True),
    ("1020", "Cheques Receivable", "asset", False, False),
    ("1100", "Accounts Receivable", "asset", False, False),
    ("1200", "Inventory", "asset", False, False),
    ("1300", "Input Tax", "asset", False, False),
    ("2000", "Accounts Payable", "liability", False, False),
    ("2015", "Cheques Payable", "liability", False, False),
    ("2100", "Tax Payable", "liability", False, False),
    ("3000", "Owner Equity", "equity", False, False),
    ("3900", "Opening Balances Equity", "equity", False, False),
    ("4000", "Sales Revenue", "income", False, False),
    ("4100", "Sales Discounts", "expense", False, False),
    ("4200", "Purchase Discounts Taken", "income", False, False),
    ("4300", "FX Gain/Loss", "income", False, False),
    ("5000", "Cost of Goods Sold", "expense", False, False),
    ("6000", "Operating Expenses", "expense", False, False),
]

ACCOUNT_TYPES = frozenset({"asset", "liability", "equity", "income", "expense"})
OPENING_BALANCE_EQUITY_CODE = "3900"
SYSTEM_ACCOUNT_CODES = frozenset(code for code, *_ in DEFAULT_ACCOUNTS)


def lines_are_balanced(lines: list[dict], tolerance: float = 0.01) -> bool:
    debit = sum(float(x.get("debit") or 0) for x in lines)
    credit = sum(float(x.get("credit") or 0) for x in lines)
    return abs(debit - credit) <= tolerance


# Methods that settle through the bank GL (1010) rather than till cash (1000).
BANK_SETTLEMENT_METHODS = frozenset(
    {
        "bank_transfer",
        "bank",
        "transfer",
        "card",
        "credit_card",
        "debit_card",
        "wallet",
        "ach",
        "wire",
        "eft",
        "online",
    }
)

CHEQUE_METHODS = frozenset({"cheque", "check"})
# Allowed settlement overrides beyond cash/bank flags (cheque clearing).
SETTLEMENT_OVERRIDE_CODES = frozenset({"1000", "1010", "1020", "2015"})


def is_cheque_method(payment_method: str | None) -> bool:
    method = (payment_method or "").strip().lower().replace("-", "_").replace(" ", "_")
    return method in CHEQUE_METHODS


def liquid_gl_for_payment_method(payment_method: str | None) -> tuple[str, str]:
    """Map payment method → (GL code, label) for cash/bank settlement.

    - cash / unknown → 1000 Cash
    - bank_transfer, card, wallet, … → 1010 Bank
    - cheque/check → 1020 Cheques Receivable (clearing; lifecycle moves to Bank)
    - credit (AR) is not a liquid settlement; callers handle separately
    """
    method = (payment_method or "cash").strip().lower().replace("-", "_").replace(" ", "_")
    if method in CHEQUE_METHODS:
        return "1020", "Cheques Receivable"
    if method in BANK_SETTLEMENT_METHODS:
        return "1010", "Bank"
    return "1000", "Cash"


def supplier_payment_credit_gl(payment_method: str | None) -> tuple[str, str]:
    """Credit side for supplier/expense outflows."""
    if is_cheque_method(payment_method):
        return "2015", "Cheques Payable"
    return liquid_gl_for_payment_method(payment_method)


def pos_debit_account_for_payment_method(payment_method: str | None) -> tuple[str, str]:
    """POS receivable side: cash till, bank (card/etc), cheques clearing, or AR for credit sales."""
    method = (payment_method or "cash").strip().lower()
    if method == "credit":
        return "1100", "AR"
    return liquid_gl_for_payment_method(method)


def _account_is_settlement_eligible(account: m.Account, *, outflow: bool) -> bool:
    if account.is_cash_account or account.is_bank_account:
        return True
    if account.code in SETTLEMENT_OVERRIDE_CODES:
        if outflow and account.code == "1020":
            return False
        if not outflow and account.code == "2015":
            return False
        return True
    return False


async def resolve_settlement_gl(
    db: AsyncSession,
    tenant_id: str,
    payment_method: str | None,
    *,
    liquid_account_id: str | None = None,
    outflow: bool = False,
) -> tuple[str, str]:
    """Resolve (account_code, label), honoring optional per-payment liquid account override."""
    await ensure_default_accounts(db, tenant_id)
    if liquid_account_id:
        account = (
            await db.execute(
                select(m.Account).where(
                    m.Account.id == liquid_account_id,
                    m.Account.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Settlement account not found")
        if not _account_is_settlement_eligible(account, outflow=outflow):
            raise HTTPException(
                status_code=400,
                detail="Account is not a cash/bank/settlement account for this payment direction",
            )
        return account.code, account.name
    if outflow:
        return supplier_payment_credit_gl(payment_method)
    return liquid_gl_for_payment_method(payment_method)


async def get_account_by_code(
    db: AsyncSession, tenant_id: str, code: str, *, company_id: str | None = None
) -> m.Account:
    q = select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == code)
    if company_id:
        account = (
            await db.execute(q.where(m.Account.company_id == company_id))
        ).scalar_one_or_none()
        if account:
            return account
        # Legacy / pre-scope rows: allow null company_id accounts for the same code.
        account = (
            await db.execute(q.where(m.Account.company_id.is_(None)))
        ).scalar_one_or_none()
        if account:
            return account
        raise HTTPException(status_code=400, detail=f"Account code {code} not found for tenant")
    account = (await db.execute(q.limit(1))).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=400, detail=f"Account code {code} not found for tenant")
    return account


async def ensure_default_accounts(
    db: AsyncSession, tenant_id: str, company_id: str | None = None
) -> None:
    q = select(m.Account).where(m.Account.tenant_id == tenant_id)
    if company_id:
        q = q.where(m.Account.company_id == company_id)
    existing = {
        a.code: a
        for a in (await db.execute(q)).scalars().all()
    }
    for code, name, account_type, is_cash, is_bank in DEFAULT_ACCOUNTS:
        if code not in existing:
            db.add(
                m.Account(
                    tenant_id=tenant_id,
                    company_id=company_id,
                    code=code,
                    name=name,
                    account_type=account_type,
                    balance=0,
                    is_cash_account=is_cash,
                    is_bank_account=is_bank,
                    is_system=True,
                    is_active=True,
                )
            )
        else:
            row = existing[code]
            row.is_system = True
            # Keep flags aligned for seeded liquid accounts without clobbering custom flags on others
            if code == "1000":
                row.is_cash_account = True
            if code == "1010":
                row.is_bank_account = True
    await db.flush()


def serialize_coa_account(account: m.Account) -> dict:
    return {
        "id": account.id,
        "code": account.code,
        "name": account.name,
        "account_type": account.account_type,
        "parent_id": account.parent_id,
        "balance": float(account.balance or 0),
        "is_cash_account": bool(account.is_cash_account),
        "is_bank_account": bool(account.is_bank_account),
        "is_system": bool(getattr(account, "is_system", False)),
        "is_active": bool(getattr(account, "is_active", True)),
        "bank_name": account.bank_name,
        "account_number": account.account_number,
        "bank_branch": getattr(account, "bank_branch", None),
    }


def build_account_tree(rows: list[m.Account]) -> list[dict]:
    """Nest accounts by parent_id; orphans with missing parents become roots."""
    by_id = {r.id: {**serialize_coa_account(r), "children": []} for r in rows}
    roots: list[dict] = []
    for r in rows:
        node = by_id[r.id]
        parent_id = r.parent_id
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(node)
        else:
            roots.append(node)

    def sort_rec(nodes: list[dict]) -> None:
        nodes.sort(key=lambda n: n["code"])
        for n in nodes:
            sort_rec(n["children"])

    sort_rec(roots)
    return roots


async def get_tenant_account(
    db: AsyncSession, tenant_id: str, account_id: str
) -> m.Account:
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


def _natural_side_delta(account_type: str, debit: float, credit: float) -> float:
    """Signed movement on the account's natural balance side."""
    if account_type in {"asset", "expense"}:
        return float(debit) - float(credit)
    return float(credit) - float(debit)


async def account_transactions(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    include_unposted: bool = False,
) -> dict:
    """Ledger drill-down for one COA account (Stage 8 A1)."""
    account = await get_tenant_account(db, tenant_id, account_id)
    stmt = (
        select(m.JournalEntryLine, m.JournalEntry)
        .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntry.tenant_id == tenant_id,
            m.JournalEntryLine.account_id == account_id,
        )
    )
    if not include_unposted:
        stmt = stmt.where(m.JournalEntry.status == "posted")
    stmt = stmt.order_by(
        m.JournalEntry.entry_date.asc(),
        m.JournalEntry.entry_number.asc(),
        m.JournalEntryLine.id.asc(),
    )
    rows = (await db.execute(stmt)).all()

    opening = 0.0
    period_rows: list[tuple[m.JournalEntryLine, m.JournalEntry]] = []
    for line, entry in rows:
        entry_dt = entry.entry_date or entry.created_at or datetime.utcnow()
        if from_date and entry_dt < from_date:
            opening = round(
                opening
                + _natural_side_delta(
                    account.account_type, float(line.debit or 0), float(line.credit or 0)
                ),
                2,
            )
            continue
        if to_date and entry_dt > to_date:
            continue
        period_rows.append((line, entry))

    running = opening
    transactions: list[dict] = []
    total_debit = 0.0
    total_credit = 0.0
    for line, entry in period_rows:
        debit = float(line.debit or 0)
        credit = float(line.credit or 0)
        total_debit = round(total_debit + debit, 2)
        total_credit = round(total_credit + credit, 2)
        running = round(
            running + _natural_side_delta(account.account_type, debit, credit), 2
        )
        transactions.append(
            {
                "line_id": line.id,
                "journal_entry_id": entry.id,
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date,
                "reference": entry.reference,
                "description": line.description or entry.description,
                "source_type": entry.source_type,
                "source_id": entry.source_id,
                "status": entry.status,
                "debit": debit,
                "credit": credit,
                "balance": running,
            }
        )

    return {
        "account": serialize_coa_account(account),
        "from_date": from_date.date().isoformat() if from_date else None,
        "to_date": to_date.date().isoformat() if to_date else None,
        "include_unposted": bool(include_unposted),
        "opening_balance": opening,
        "closing_balance": running,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "transaction_count": len(transactions),
        "transactions": transactions,
    }


async def _validate_parent(
    db: AsyncSession,
    *,
    tenant_id: str,
    account_type: str,
    parent_id: str | None,
    self_id: str | None = None,
) -> None:
    if not parent_id:
        return
    if self_id and parent_id == self_id:
        raise HTTPException(status_code=400, detail="Account cannot be its own parent")
    parent = await get_tenant_account(db, tenant_id, parent_id)
    if parent.account_type != account_type:
        raise HTTPException(
            status_code=400,
            detail="Parent account must have the same account_type",
        )
    if self_id:
        cursor = parent
        seen = {self_id}
        while cursor is not None:
            if cursor.id in seen:
                raise HTTPException(
                    status_code=400, detail="Account parent would create a cycle"
                )
            seen.add(cursor.id)
            if not cursor.parent_id:
                break
            cursor = (
                await db.execute(
                    select(m.Account).where(
                        m.Account.id == cursor.parent_id,
                        m.Account.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()


async def create_coa_account(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    account_type: str,
    parent_id: str | None = None,
    company_id: str | None = None,
) -> m.Account:
    await ensure_default_accounts(db, tenant_id, company_id=company_id)
    type_norm = (account_type or "").strip().lower()
    if type_norm not in ACCOUNT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"account_type must be one of {sorted(ACCOUNT_TYPES)}",
        )
    code_norm = (code or "").strip()
    name_norm = (name or "").strip()
    if not code_norm or not name_norm:
        raise HTTPException(status_code=400, detail="code and name are required")

    existing_q = select(m.Account).where(
        m.Account.tenant_id == tenant_id, m.Account.code == code_norm
    )
    if company_id:
        existing_q = existing_q.where(m.Account.company_id == company_id)
    existing = (await db.execute(existing_q)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Account code {code_norm} already exists")

    await _validate_parent(
        db, tenant_id=tenant_id, account_type=type_norm, parent_id=parent_id
    )

    row = m.Account(
        tenant_id=tenant_id,
        company_id=company_id,
        code=code_norm,
        name=name_norm,
        account_type=type_norm,
        parent_id=parent_id,
        balance=0,
        is_system=False,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def update_coa_account(
    db: AsyncSession,
    *,
    tenant_id: str,
    account_id: str,
    code: str | None = None,
    name: str | None = None,
    account_type: str | None = None,
    parent_id: str | None = None,
    is_active: bool | None = None,
    clear_parent: bool = False,
) -> m.Account:
    row = await get_tenant_account(db, tenant_id, account_id)
    if row.is_system and (code is not None or account_type is not None or name is not None):
        # System accounts: only parent/active structural fields may change via dedicated paths.
        # Name/code/type edits are reserved for non-system accounts (BR-10.1).
        if code is not None or account_type is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "SYSTEM_ACCOUNT",
                    "message": "Cannot change code or type of a system account",
                },
            )
        if name is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "SYSTEM_ACCOUNT",
                    "message": "Cannot edit name of a system account",
                },
            )

    if code is not None:
        code_norm = code.strip()
        if not code_norm:
            raise HTTPException(status_code=400, detail="code cannot be empty")
        dup = (
            await db.execute(
                select(m.Account).where(
                    m.Account.tenant_id == tenant_id,
                    m.Account.code == code_norm,
                    m.Account.id != row.id,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=409, detail=f"Account code {code_norm} already exists")
        row.code = code_norm

    if name is not None:
        name_norm = name.strip()
        if not name_norm:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        row.name = name_norm

    if account_type is not None:
        type_norm = account_type.strip().lower()
        if type_norm not in ACCOUNT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"account_type must be one of {sorted(ACCOUNT_TYPES)}",
            )
        row.account_type = type_norm

    if clear_parent:
        row.parent_id = None
    elif parent_id is not None:
        await _validate_parent(
            db,
            tenant_id=tenant_id,
            account_type=row.account_type,
            parent_id=parent_id,
            self_id=row.id,
        )
        row.parent_id = parent_id

    if is_active is not None:
        if row.is_system and not is_active:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "SYSTEM_ACCOUNT",
                    "message": "Cannot deactivate a system account",
                },
            )
        row.is_active = bool(is_active)

    await db.flush()
    return row


async def post_account_opening_balance(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    account_id: str,
    amount: float,
    description: str | None = None,
) -> m.JournalEntry:
    """Post a balanced opening-balance journal for one account (BR-10.1)."""
    await ensure_default_accounts(db, tenant_id)
    account = await get_tenant_account(db, tenant_id, account_id)
    if not account.is_active:
        raise HTTPException(status_code=400, detail="Account is inactive")
    if account.code == OPENING_BALANCE_EQUITY_CODE:
        raise HTTPException(
            status_code=400,
            detail="Cannot set an opening balance on the Opening Balances Equity account",
        )

    amt = round(float(amount), 2)
    if amt == 0:
        raise HTTPException(status_code=400, detail="amount must be non-zero")

    prior = (
        await db.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "opening_balance",
                m.JournalEntry.source_id == account.id,
                m.JournalEntry.status == "posted",
            )
        )
    ).scalar_one_or_none()
    if prior:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "OPENING_BALANCE_EXISTS",
                "message": "Posted opening balance already exists for this account; unpost it first",
                "journal_entry_id": prior.id,
            },
        )

    equity = await get_account_by_code(db, tenant_id, OPENING_BALANCE_EQUITY_CODE)
    abs_amt = abs(amt)
    # Natural side: assets/expenses debit-positive; liability/equity/income credit-positive.
    # Negative amount flips the side (e.g. credit balance on an asset).
    natural_debit = account.account_type in {"asset", "expense"}
    account_debit = natural_debit if amt > 0 else not natural_debit

    if account_debit:
        lines = [
            {
                "account_id": account.id,
                "debit": abs_amt,
                "credit": 0,
                "description": "Opening balance",
            },
            {
                "account_id": equity.id,
                "debit": 0,
                "credit": abs_amt,
                "description": f"Opening balance offset {account.code}",
            },
        ]
    else:
        lines = [
            {
                "account_id": equity.id,
                "debit": abs_amt,
                "credit": 0,
                "description": f"Opening balance offset {account.code}",
            },
            {
                "account_id": account.id,
                "debit": 0,
                "credit": abs_amt,
                "description": "Opening balance",
            },
        ]

    desc = (description or "").strip() or f"Opening balance {account.code} {account.name}"
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=desc,
        reference=f"OB-{account.code}",
        source_type="opening_balance",
        source_id=account.id,
        lines=lines,
    )


def _infer_liquid_move_kind(from_acct: m.Account, to_acct: m.Account) -> str:
    if from_acct.is_cash_account and to_acct.is_bank_account:
        return "deposit"
    if from_acct.is_bank_account and to_acct.is_cash_account:
        return "withdrawal"
    return "transfer"


async def create_liquid_account(
    db: AsyncSession,
    *,
    tenant_id: str,
    kind: str,
    code: str,
    name: str,
    bank_name: str | None = None,
    account_number: str | None = None,
    bank_branch: str | None = None,
) -> m.Account:
    await ensure_default_accounts(db, tenant_id)
    kind_norm = (kind or "").strip().lower()
    if kind_norm not in {"cash", "bank"}:
        raise HTTPException(status_code=400, detail="kind must be cash or bank")
    code_norm = (code or "").strip()
    name_norm = (name or "").strip()
    if not code_norm or not name_norm:
        raise HTTPException(status_code=400, detail="code and name are required")

    existing = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == code_norm)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Account code {code_norm} already exists")

    is_cash = kind_norm == "cash"
    is_bank = kind_norm == "bank"
    if is_bank and not (bank_name or "").strip():
        raise HTTPException(status_code=400, detail="bank_name is required for bank accounts")

    row = m.Account(
        tenant_id=tenant_id,
        code=code_norm,
        name=name_norm,
        account_type="asset",
        balance=0,
        is_cash_account=is_cash,
        is_bank_account=is_bank,
        is_system=False,
        is_active=True,
        bank_name=((bank_name or "").strip() or None) if is_bank else None,
        account_number=((account_number or "").strip() or None) if is_bank else None,
        bank_branch=((bank_branch or "").strip() or None) if is_bank else None,
    )
    db.add(row)
    await db.flush()
    return row


async def update_liquid_account(
    db: AsyncSession,
    *,
    tenant_id: str,
    account_id: str,
    name: str | None = None,
    bank_name: str | None = None,
    account_number: str | None = None,
    bank_branch: str | None = None,
    clear_bank_details: bool | None = None,
    is_active: bool | None = None,
) -> m.Account:
    from app.bank_recon import get_liquid_account

    row = await get_liquid_account(db, tenant_id, account_id)
    if name is not None:
        name_norm = name.strip()
        if not name_norm:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        row.name = name_norm
    if clear_bank_details:
        row.bank_name = None
        row.account_number = None
        row.bank_branch = None
    if bank_name is not None:
        row.bank_name = bank_name.strip() or None
    if account_number is not None:
        row.account_number = account_number.strip() or None
    if bank_branch is not None:
        row.bank_branch = bank_branch.strip() or None
    if is_active is not None:
        row.is_active = bool(is_active)
    if row.is_bank_account and not (row.bank_name or "").strip() and row.is_active:
        raise HTTPException(status_code=400, detail="bank_name is required for bank accounts")
    await db.flush()
    return row


async def transfer_liquid_funds(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    from_account_id: str,
    to_account_id: str,
    amount: float,
    description: str | None = None,
    reference: str | None = None,
    kind: str | None = None,
) -> m.JournalEntry:
    """Move funds between cash/bank accounts (deposit, withdrawal, or transfer)."""
    from app.bank_recon import get_liquid_account

    await ensure_default_accounts(db, tenant_id)
    amt = round(float(amount), 2)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    if from_account_id == to_account_id:
        raise HTTPException(status_code=400, detail="from_account_id and to_account_id must differ")

    from_acct = await get_liquid_account(db, tenant_id, from_account_id)
    to_acct = await get_liquid_account(db, tenant_id, to_account_id)

    inferred = _infer_liquid_move_kind(from_acct, to_acct)
    kind_norm = (kind or inferred).strip().lower()
    if kind_norm not in {"deposit", "withdrawal", "transfer"}:
        raise HTTPException(
            status_code=400,
            detail="kind must be deposit, withdrawal, or transfer",
        )
    if kind_norm == "deposit" and not (from_acct.is_cash_account and to_acct.is_bank_account):
        raise HTTPException(status_code=400, detail="deposit requires cash → bank")
    if kind_norm == "withdrawal" and not (from_acct.is_bank_account and to_acct.is_cash_account):
        raise HTTPException(status_code=400, detail="withdrawal requires bank → cash")

    default_desc = {
        "deposit": f"Deposit {from_acct.code} → {to_acct.code}",
        "withdrawal": f"Withdrawal {from_acct.code} → {to_acct.code}",
        "transfer": f"Transfer {from_acct.code} → {to_acct.code}",
    }[kind_norm]
    desc = (description or "").strip() or default_desc

    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=desc,
        reference=reference,
        source_type=f"liquid_{kind_norm}",
        source_id=None,
        lines=[
            {
                "account_id": to_acct.id,
                "debit": amt,
                "credit": 0,
                "description": desc,
            },
            {
                "account_id": from_acct.id,
                "debit": 0,
                "credit": amt,
                "description": desc,
            },
        ],
    )


def _signed_balance_delta(account_type: str, debit: float, credit: float) -> float:
    """Update running balance: assets/expenses increase with debit; liability/income/equity with credit."""
    if account_type in {"asset", "expense"}:
        return debit - credit
    return credit - debit


def _parse_fiscal_mm_dd(fiscal_year_start: str) -> tuple[int, int]:
    raw = (fiscal_year_start or "01-01").strip()
    parts = raw.split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="fiscal_year_start must be MM-DD")
    try:
        month, day = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="fiscal_year_start must be MM-DD") from exc
    if month < 1 or month > 12 or day < 1 or day > 31:
        raise HTTPException(status_code=400, detail="fiscal_year_start must be MM-DD")
    return month, day


def _safe_date(year: int, month: int, day: int) -> date:
    """Clamp day for short months (e.g. Feb 29 → Feb 28 on non-leap years)."""
    from calendar import monthrange

    last = monthrange(year, month)[1]
    return date(year, month, min(day, last))


def fiscal_year_bounds(
    fiscal_year_start: str,
    *,
    as_of: date | datetime | None = None,
) -> tuple[date, date]:
    """Return [start, end) for the open fiscal year containing as_of."""
    if as_of is None:
        as_of_d = datetime.utcnow().date()
    elif isinstance(as_of, datetime):
        as_of_d = as_of.date()
    else:
        as_of_d = as_of
    month, day = _parse_fiscal_mm_dd(fiscal_year_start)
    start = _safe_date(as_of_d.year, month, day)
    if as_of_d < start:
        start = _safe_date(as_of_d.year - 1, month, day)
    end = _safe_date(start.year + 1, month, day)
    return start, end


def entry_in_open_fiscal_period(
    entry_date: date | datetime,
    fiscal_year_start: str,
    *,
    as_of: date | datetime | None = None,
) -> bool:
    start, end = fiscal_year_bounds(fiscal_year_start, as_of=as_of)
    ed = entry_date.date() if isinstance(entry_date, datetime) else entry_date
    return start <= ed < end


def _closed_period_starts(tenant: m.Tenant) -> list[str]:
    raw = getattr(tenant, "fiscal_closed_period_starts", None) or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


def fiscal_period_manually_closed(
    tenant: m.Tenant,
    entry_date: date | datetime,
) -> bool:
    """Stage 118 F1 — True when the FY containing entry_date was closed via the console."""
    fys = tenant.fiscal_year_start or "01-01"
    start, _end = fiscal_year_bounds(fys, as_of=entry_date)
    return start.isoformat() in _closed_period_starts(tenant)


def assert_fiscal_period_open_for_mutation(
    tenant: m.Tenant,
    entry_date: date | datetime,
) -> None:
    """Block post/unpost when calendar period is past OR current FY was manually closed."""
    fys = tenant.fiscal_year_start or "01-01"
    start, end = fiscal_year_bounds(fys)
    if not entry_in_open_fiscal_period(entry_date, fys) or fiscal_period_manually_closed(
        tenant, entry_date
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "FISCAL_PERIOD_CLOSED",
                "message": "Mutation is only allowed within an open fiscal period",
                "open_period_start": start.isoformat(),
                "open_period_end_exclusive": end.isoformat(),
                "current_period_closed": start.isoformat() in _closed_period_starts(tenant),
            },
        )


def serialize_fiscal_period_status(tenant: m.Tenant) -> dict:
    fys = tenant.fiscal_year_start or "01-01"
    start, end = fiscal_year_bounds(fys)
    closed_starts = _closed_period_starts(tenant)
    return {
        "fiscal_year_start": fys,
        "open_period_start": start.isoformat(),
        "open_period_end_exclusive": end.isoformat(),
        "current_period_closed": start.isoformat() in closed_starts,
        "closed_period_starts": closed_starts,
    }


async def close_current_fiscal_period(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
) -> dict:
    """Stage 118 F1 — lock the calendar-open fiscal year for post/unpost mutations."""
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    fys = tenant.fiscal_year_start or "01-01"
    start, end = fiscal_year_bounds(fys)
    closed = list(_closed_period_starts(tenant))
    key = start.isoformat()
    if key not in closed:
        closed.append(key)
        tenant.fiscal_closed_period_starts = closed
        from sqlalchemy.orm.attributes import flag_modified

        flag_modified(tenant, "fiscal_closed_period_starts")
        from app import audit as audit_svc

        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            module="accounting",
            action="fiscal_period_close",
            entity="tenant",
            entity_id=tenant_id,
            details={
                "period_start": key,
                "period_end_exclusive": end.isoformat(),
            },
        )
    return serialize_fiscal_period_status(tenant)


async def reopen_current_fiscal_period(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
) -> dict:
    """Stage 118 F1 — reopen the calendar-open fiscal year (company admin)."""
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    fys = tenant.fiscal_year_start or "01-01"
    start, end = fiscal_year_bounds(fys)
    key = start.isoformat()
    closed = [x for x in _closed_period_starts(tenant) if x != key]
    tenant.fiscal_closed_period_starts = closed
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(tenant, "fiscal_closed_period_starts")
    from app import audit as audit_svc

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="accounting",
        action="fiscal_period_reopen",
        entity="tenant",
        entity_id=tenant_id,
        details={
            "period_start": key,
            "period_end_exclusive": end.isoformat(),
        },
    )
    return serialize_fiscal_period_status(tenant)


async def unpost_journal_entry(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    entry_id: str,
) -> m.JournalEntry:
    """Reverse a posted journal within the open fiscal period (BR-10.2)."""
    entry = (
        await db.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.id == entry_id,
                m.JournalEntry.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    if (entry.status or "").lower() != "posted":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "JOURNAL_NOT_POSTED",
                "message": f"Only posted journals can be unposted (status={entry.status})",
            },
        )

    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    assert_fiscal_period_open_for_mutation(tenant, entry.entry_date)

    lines = (
        await db.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.tenant_id == tenant_id,
                m.JournalEntryLine.journal_entry_id == entry.id,
            )
        )
    ).scalars().all()
    if not lines:
        raise HTTPException(status_code=400, detail="Journal entry has no lines")

    line_ids = [ln.id for ln in lines]
    matched = (
        await db.execute(
            select(m.BankStatementLine.id)
            .where(
                m.BankStatementLine.tenant_id == tenant_id,
                m.BankStatementLine.matched_journal_line_id.in_(line_ids),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    clearing_link = (
        await db.execute(
            select(m.BankClearingBookLink.id)
            .where(
                m.BankClearingBookLink.tenant_id == tenant_id,
                m.BankClearingBookLink.journal_line_id.in_(line_ids),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if matched or clearing_link:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "JOURNAL_RECONCILED",
                "message": "Cannot unpost a journal with bank-reconciled lines; unmatch first",
            },
        )

    for line in lines:
        account = (
            await db.execute(
                select(m.Account).where(
                    m.Account.id == line.account_id,
                    m.Account.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        account.balance = float(account.balance or 0) - _signed_balance_delta(
            account.account_type, float(line.debit or 0), float(line.credit or 0)
        )

    entry.status = "unposted"

    from app import audit as audit_svc

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="journal_unposted",
        entity="journal_entry",
        entity_id=entry.id,
        details={
            "entry_number": entry.entry_number,
            "total_debit": float(entry.total_debit or 0),
            "source_type": entry.source_type,
            "source_id": entry.source_id,
        },
        module="accounting",
    )
    return entry


async def resolve_journal_store_id(
    db: AsyncSession, *, tenant_id: str, store_id: str | None
) -> str | None:
    """Validate optional store dimension (tenant-scoped 404)."""
    if not store_id:
        return None
    from app.stores import get_store

    store = await get_store(db, tenant_id, store_id)
    return store.id


async def resolve_journal_dimension_ids(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str | None = None,
    branch_id: str | None = None,
) -> tuple[str | None, str | None, list[str] | None]:
    """Resolve optional store/branch journal filters.

    Returns ``(store_id, branch_id, store_ids)`` where ``store_ids`` is:
    - ``None`` — no dimension filter
    - ``list`` — filter journals to those store ids (may be empty)
    """
    from app.org_units import get_branch
    from app.stores import get_store

    resolved_branch: str | None = None
    resolved_store: str | None = None
    if branch_id:
        branch = await get_branch(db, tenant_id, branch_id)
        resolved_branch = branch.id
    if store_id:
        store = await get_store(db, tenant_id, store_id)
        resolved_store = store.id
        if resolved_branch and store.branch_id != resolved_branch:
            raise HTTPException(
                status_code=400,
                detail="STORE_BRANCH_MISMATCH: Store does not belong to the selected branch",
            )
        return resolved_store, resolved_branch, [resolved_store]
    if resolved_branch:
        stores = (
            await db.execute(
                select(m.Store).where(
                    m.Store.tenant_id == tenant_id,
                    m.Store.branch_id == resolved_branch,
                )
            )
        ).scalars().all()
        return None, resolved_branch, [s.id for s in stores]
    return None, None, None


async def post_journal_entry(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    description: str,
    lines: list[dict],
    reference: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    store_id: str | None = None,
    company_id: str | None = None,
) -> m.JournalEntry:
    if len(lines) < 2:
        raise HTTPException(status_code=400, detail="Journal entry requires at least two lines")

    normalized = []
    for line in lines:
        debit = float(line.get("debit") or 0)
        credit = float(line.get("credit") or 0)
        if debit < 0 or credit < 0:
            raise HTTPException(status_code=400, detail="Debit/credit cannot be negative")
        if debit == 0 and credit == 0:
            raise HTTPException(status_code=400, detail="Each line needs a debit or credit amount")
        if debit > 0 and credit > 0:
            raise HTTPException(status_code=400, detail="A line cannot have both debit and credit")
        if not line.get("account_id") and not line.get("account_code"):
            raise HTTPException(status_code=400, detail="Each line needs account_id or account_code")
        normalized.append({**line, "debit": debit, "credit": credit})

    if not lines_are_balanced(normalized):
        raise HTTPException(status_code=400, detail="Journal entry is not balanced")

    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    # Stage 118 F1 — block posting into a manually closed current fiscal period
    assert_fiscal_period_open_for_mutation(tenant, datetime.utcnow())

    total_debit = sum(x["debit"] for x in normalized)
    total_credit = sum(x["credit"] for x in normalized)
    resolved_store = await resolve_journal_store_id(db, tenant_id=tenant_id, store_id=store_id)

    entry = m.JournalEntry(
        tenant_id=tenant_id,
        company_id=company_id,
        entry_number=f"JE-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        reference=reference,
        description=description,
        source_type=source_type,
        source_id=source_id,
        store_id=resolved_store,
        total_debit=total_debit,
        total_credit=total_credit,
        status="posted",
        created_by=user_id,
    )
    db.add(entry)
    await db.flush()

    for line in normalized:
        account = None
        if line.get("account_id"):
            account = (
                await db.execute(
                    select(m.Account).where(
                        m.Account.id == line["account_id"],
                        m.Account.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if (
                account
                and company_id
                and account.company_id
                and account.company_id != company_id
            ):
                account = None
        else:
            account = await get_account_by_code(
                db, tenant_id, line["account_code"], company_id=company_id
            )
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        db.add(
            m.JournalEntryLine(
                tenant_id=tenant_id,
                company_id=company_id,
                journal_entry_id=entry.id,
                account_id=account.id,
                debit=line["debit"],
                credit=line["credit"],
                description=line.get("description"),
            )
        )
        account.balance = float(account.balance or 0) + _signed_balance_delta(
            account.account_type, line["debit"], line["credit"]
        )

    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="journal_posted",
        entity="journal_entry",
        entity_id=entry.id,
        details={
        "entry_number": entry.entry_number,
        "total_debit": total_debit,
        "source_type": source_type,
        "source_id": source_id,
        },
        module='accounting',
    )
    return entry


async def serialize_journal(db: AsyncSession, entry: m.JournalEntry) -> dict:
    lines = (
        await db.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.tenant_id == entry.tenant_id,
                m.JournalEntryLine.journal_entry_id == entry.id,
            )
        )
    ).scalars().all()
    return {
        "id": entry.id,
        "entry_number": entry.entry_number,
        "entry_date": entry.entry_date,
        "reference": entry.reference,
        "description": entry.description,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "store_id": getattr(entry, "store_id", None),
        "total_debit": float(entry.total_debit),
        "total_credit": float(entry.total_credit),
        "status": entry.status,
        "attachment_url": entry.attachment_url,
        "has_attachment": bool(entry.attachment_url),
        "created_by": entry.created_by,
        "created_at": entry.created_at,
        "balanced": abs(float(entry.total_debit) - float(entry.total_credit)) < 0.01,
        "lines": [
            {
                "id": ln.id,
                "account_id": ln.account_id,
                "debit": float(ln.debit),
                "credit": float(ln.credit),
                "description": ln.description,
            }
            for ln in lines
        ],
    }


async def unit_standard_cost(
    db: AsyncSession,
    tenant_id: str,
    *,
    product_id: str | None,
    variant_id: str | None = None,
) -> float:
    """Standard cost from variant (if set) else product; tenant-scoped."""
    if not product_id:
        return 0.0
    if variant_id:
        variant = await db.get(m.ProductVariant, variant_id)
        if variant and variant.tenant_id == tenant_id:
            cost = float(variant.cost_price or 0)
            if cost > 0:
                return cost
    product = await db.get(m.Product, product_id)
    if product and product.tenant_id == tenant_id:
        return max(float(product.cost_price or 0), 0.0)
    return 0.0


async def standard_cost_cogs_for_lines(
    db: AsyncSession,
    tenant_id: str,
    lines: list,
) -> float:
    """Sum qty × standard cost for invoice/POS/return line dicts or ORM rows."""
    total = 0.0
    for line in lines:
        if isinstance(line, dict):
            qty = float(line.get("quantity") or 0)
            product_id = line.get("product_id")
            variant_id = line.get("variant_id")
        else:
            qty = float(getattr(line, "quantity", 0) or 0)
            product_id = getattr(line, "product_id", None)
            variant_id = getattr(line, "variant_id", None)
        if qty <= 0 or not product_id:
            continue
        unit = await unit_standard_cost(
            db, tenant_id, product_id=str(product_id), variant_id=str(variant_id) if variant_id else None
        )
        if unit > 0:
            total += qty * unit
    return round(total, 2)


def cogs_inventory_journal_lines(cogs: float, *, reverse: bool = False) -> list[dict]:
    """Dr COGS 5000 / Cr Inventory 1200 (sale), or reverse for restocked returns."""
    amount = round(float(cogs or 0), 2)
    if amount <= 0:
        return []
    if reverse:
        return [
            {
                "account_code": "1200",
                "debit": amount,
                "credit": 0,
                "description": "Inventory restock",
            },
            {
                "account_code": "5000",
                "debit": 0,
                "credit": amount,
                "description": "COGS reverse",
            },
        ]
    return [
        {"account_code": "5000", "debit": amount, "credit": 0, "description": "COGS"},
        {
            "account_code": "1200",
            "debit": 0,
            "credit": amount,
            "description": "Inventory out",
        },
    ]


async def post_sales_invoice_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice: m.SalesInvoice,
) -> m.JournalEntry:
    await ensure_default_accounts(db, tenant_id)
    from app.fx import doc_rate, to_base

    rate = doc_rate(invoice)
    revenue = to_base(float(invoice.subtotal) - float(invoice.discount_amount or 0), rate)
    tax = to_base(float(invoice.tax_amount or 0), rate)
    total = to_base(float(invoice.total_amount), rate)
    lines = [
        {"account_code": "1100", "debit": total, "credit": 0, "description": "AR"},
        {"account_code": "4000", "debit": 0, "credit": max(revenue, 0), "description": "Sales"},
    ]
    if tax > 0:
        lines.append({"account_code": "2100", "debit": 0, "credit": tax, "description": "Tax"})
    if revenue < 0:
        raise HTTPException(status_code=400, detail="Invoice revenue after discount cannot be negative")

    items = (
        await db.execute(
            select(m.SalesInvoiceItem).where(
                m.SalesInvoiceItem.tenant_id == tenant_id,
                m.SalesInvoiceItem.sales_invoice_id == invoice.id,
            )
        )
    ).scalars().all()
    cogs = await standard_cost_cogs_for_lines(db, tenant_id, list(items))
    lines.extend(cogs_inventory_journal_lines(cogs))

    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Sales invoice {invoice.invoice_number}",
        reference=invoice.invoice_number,
        source_type="sales_invoice",
        source_id=invoice.id,
        store_id=getattr(invoice, "store_id", None),
        lines=lines,
    )


async def post_sales_return_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    sales_return: m.SalesReturn,
    invoice: m.SalesInvoice | None = None,
) -> m.JournalEntry:
    await ensure_default_accounts(db, tenant_id)
    from app.fx import doc_rate, to_base

    if invoice is None:
        invoice = (
            await db.execute(
                select(m.SalesInvoice).where(
                    m.SalesInvoice.id == sales_return.sales_invoice_id,
                    m.SalesInvoice.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    rate = doc_rate(invoice) if invoice is not None else 1.0
    revenue = to_base(float(sales_return.subtotal or 0), rate)
    tax = to_base(float(sales_return.tax_amount or 0), rate)
    total = to_base(float(sales_return.total_amount), rate)
    lines = [
        {"account_code": "4000", "debit": max(revenue, 0), "credit": 0, "description": "Sales return"},
        {"account_code": "1100", "debit": 0, "credit": total, "description": "AR credit"},
    ]
    if tax > 0:
        lines.append({"account_code": "2100", "debit": tax, "credit": 0, "description": "Tax reverse"})

    # Reverse COGS/Inventory only for restocked sellable lines (Stage 15 I1).
    if getattr(sales_return, "restock", True):
        items = (
            await db.execute(
                select(m.SalesReturnItem).where(
                    m.SalesReturnItem.tenant_id == tenant_id,
                    m.SalesReturnItem.sales_return_id == sales_return.id,
                )
            )
        ).scalars().all()
        restock_lines = [
            it for it in items if (getattr(it, "condition", None) or "sellable") == "sellable"
        ]
        cogs = await standard_cost_cogs_for_lines(db, tenant_id, restock_lines)
        lines.extend(cogs_inventory_journal_lines(cogs, reverse=True))

    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Sales return {sales_return.return_number}",
        reference=sales_return.credit_note_number or sales_return.return_number,
        source_type="sales_return",
        source_id=sales_return.id,
        store_id=getattr(invoice, "store_id", None) if invoice is not None else None,
        lines=lines,
    )


async def post_customer_payment_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    payment: m.CustomerPayment,
    allocations: list[tuple[m.SalesInvoice, float, float]] | None = None,
) -> m.JournalEntry:
    """Post receipt. allocations: (invoice, settlement_doc, discount_doc) for FX per invoice rate."""
    await ensure_default_accounts(db, tenant_id)
    from app.fx import doc_rate, fx_lines_for_receipt, to_base

    amount = float(payment.amount)
    discount = float(getattr(payment, "early_payment_discount", 0) or 0)
    pay_rate = doc_rate(payment)
    liquid_code, liquid_label = await resolve_settlement_gl(
        db,
        tenant_id,
        payment.payment_method,
        liquid_account_id=getattr(payment, "liquid_account_id", None),
        outflow=False,
    )

    cash_base = to_base(amount, pay_rate)
    if allocations:
        ar_base = 0.0
        disc_base = 0.0
        cash_at_inv = 0.0
        for inv, settle, disc in allocations:
            inv_rate = doc_rate(inv)
            cash_doc = round(settle - disc, 2)
            ar_base = round(ar_base + to_base(settle, inv_rate), 2)
            disc_base = round(disc_base + to_base(disc, inv_rate), 2)
            cash_at_inv = round(cash_at_inv + to_base(cash_doc, inv_rate), 2)
        # Remeasure cash portion at payment rate vs invoice rates
        cash_base = to_base(amount, pay_rate)
        fx_amt, fx_extra = fx_lines_for_receipt(
            cash_base=cash_base, ar_base=ar_base, discount_base=disc_base
        )
    else:
        # No invoice detail: treat payment rate as both cash and AR rate
        ar_base = to_base(amount + discount, pay_rate)
        disc_base = to_base(discount, pay_rate)
        fx_amt, fx_extra = 0.0, []

    payment.fx_gain_loss = round(fx_amt, 2)
    lines = [
        {
            "account_code": liquid_code,
            "debit": cash_base,
            "credit": 0,
            "description": liquid_label,
        },
    ]
    if disc_base > 0:
        lines.append(
            {
                "account_code": "4100",
                "debit": disc_base,
                "credit": 0,
                "description": "Early payment discount",
            }
        )
    lines.append(
        {
            "account_code": "1100",
            "debit": 0,
            "credit": ar_base,
            "description": "AR",
        }
    )
    lines.extend(fx_extra)
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Customer payment {payment.payment_number}",
        reference=payment.payment_number,
        source_type="customer_payment",
        source_id=payment.id,
        lines=lines,
    )


async def post_supplier_payment_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    payment: m.SupplierPayment,
    allocations: list[tuple[m.PurchaseInvoice, float, float]] | None = None,
) -> m.JournalEntry:
    await ensure_default_accounts(db, tenant_id)
    from app.fx import doc_rate, fx_lines_for_payment, to_base

    amount = float(payment.amount)
    discount = float(getattr(payment, "early_payment_discount", 0) or 0)
    pay_rate = doc_rate(payment)
    liquid_code, liquid_label = await resolve_settlement_gl(
        db,
        tenant_id,
        payment.payment_method,
        liquid_account_id=getattr(payment, "liquid_account_id", None),
        outflow=True,
    )
    cash_base = to_base(amount, pay_rate)
    if allocations:
        ap_base = 0.0
        disc_base = 0.0
        for inv, settle, disc in allocations:
            inv_rate = doc_rate(inv)
            ap_base = round(ap_base + to_base(settle, inv_rate), 2)
            disc_base = round(disc_base + to_base(disc, inv_rate), 2)
        fx_amt, fx_extra = fx_lines_for_payment(
            cash_base=cash_base, ap_base=ap_base, discount_base=disc_base
        )
    else:
        ap_base = to_base(amount + discount, pay_rate)
        disc_base = to_base(discount, pay_rate)
        fx_amt, fx_extra = 0.0, []

    payment.fx_gain_loss = round(fx_amt, 2)
    lines = [
        {
            "account_code": "2000",
            "debit": ap_base,
            "credit": 0,
            "description": "AP",
        },
        {
            "account_code": liquid_code,
            "debit": 0,
            "credit": cash_base,
            "description": liquid_label,
        },
    ]
    if disc_base > 0:
        lines.append(
            {
                "account_code": "4200",
                "debit": 0,
                "credit": disc_base,
                "description": "Purchase discount taken",
            }
        )
    lines.extend(fx_extra)
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Supplier payment {payment.payment_number}",
        reference=payment.payment_number,
        source_type="supplier_payment",
        source_id=payment.id,
        lines=lines,
    )


async def post_grn_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    grn: m.GoodsReceipt,
    accepted_value: float,
) -> m.JournalEntry | None:
    if accepted_value <= 0:
        return None
    await ensure_default_accounts(db, tenant_id)
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"GRN {grn.grn_number}",
        reference=grn.grn_number,
        source_type="grn",
        source_id=grn.id,
        lines=[
            {"account_code": "1200", "debit": accepted_value, "credit": 0, "description": "Inventory"},
            {"account_code": "2000", "debit": 0, "credit": accepted_value, "description": "AP"},
        ],
    )


async def post_purchase_return_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    purchase_return: m.PurchaseReturn,
) -> m.JournalEntry:
    """Reverse GRN impact: Dr AP / Cr Inventory for return total (tax-inclusive inventory value)."""
    await ensure_default_accounts(db, tenant_id)
    total = float(purchase_return.total_amount)
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Purchase return {purchase_return.return_number}",
        reference=purchase_return.debit_note_number or purchase_return.return_number,
        source_type="purchase_return",
        source_id=purchase_return.id,
        lines=[
            {"account_code": "2000", "debit": total, "credit": 0, "description": "AP credit"},
            {"account_code": "1200", "debit": 0, "credit": total, "description": "Inventory out"},
        ],
    )


async def post_purchase_invoice_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    purchase_invoice: m.PurchaseInvoice,
    skip_inventory_ap: bool = False,
) -> m.JournalEntry | None:
    """Purchase bill journal.

    Manual path: Dr Inventory (+ Input Tax if RC) / Cr AP (+ Tax Payable if RC).
    Stage 11 C2 GRN-linked RC: Inv/AP already posted by GRN — post self-assess
    Dr 1300 / Cr 2100 only when ``skip_inventory_ap`` is true.
    """
    await ensure_default_accounts(db, tenant_id)
    from app.fx import doc_rate, to_base

    rate = doc_rate(purchase_invoice)
    net = to_base(
        round(
            float(purchase_invoice.subtotal or 0) - float(purchase_invoice.discount_amount or 0),
            2,
        ),
        rate,
    )
    rc = to_base(float(getattr(purchase_invoice, "reverse_charge_tax", 0) or 0), rate)
    is_rc = bool(getattr(purchase_invoice, "is_reverse_charge", False)) and rc > 0
    if skip_inventory_ap:
        if not is_rc:
            return None
        lines = [
            {"account_code": "1300", "debit": rc, "credit": 0, "description": "Input tax (RC)"},
            {
                "account_code": "2100",
                "debit": 0,
                "credit": rc,
                "description": "Tax payable (RC self-assess)",
            },
        ]
    elif is_rc:
        lines = [
            {"account_code": "1200", "debit": net, "credit": 0, "description": "Inventory/purchases"},
            {"account_code": "1300", "debit": rc, "credit": 0, "description": "Input tax (RC)"},
            {"account_code": "2000", "debit": 0, "credit": net, "description": "AP"},
            {"account_code": "2100", "debit": 0, "credit": rc, "description": "Tax payable (RC self-assess)"},
        ]
    else:
        total = to_base(float(purchase_invoice.total_amount), rate)
        tax = to_base(float(purchase_invoice.tax_amount or 0), rate)
        if tax > 0 and abs(total - (net + tax)) < 0.02:
            lines = [
                {"account_code": "1200", "debit": net, "credit": 0, "description": "Inventory/purchases"},
                {"account_code": "1300", "debit": tax, "credit": 0, "description": "Input tax"},
                {"account_code": "2000", "debit": 0, "credit": total, "description": "AP"},
            ]
        else:
            lines = [
                {"account_code": "1200", "debit": total, "credit": 0, "description": "Inventory/purchases"},
                {"account_code": "2000", "debit": 0, "credit": total, "description": "AP"},
            ]
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Purchase invoice {purchase_invoice.invoice_number}",
        reference=purchase_invoice.supplier_invoice_number or purchase_invoice.invoice_number,
        source_type="purchase_invoice",
        source_id=purchase_invoice.id,
        lines=lines,
    )


async def post_purchase_invoice_reversal_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    purchase_invoice: m.PurchaseInvoice,
    skip_inventory_ap: bool = False,
) -> m.JournalEntry | None:
    await ensure_default_accounts(db, tenant_id)
    from app.fx import doc_rate, to_base

    rate = doc_rate(purchase_invoice)
    net = to_base(
        round(
            float(purchase_invoice.subtotal or 0) - float(purchase_invoice.discount_amount or 0),
            2,
        ),
        rate,
    )
    rc = to_base(float(getattr(purchase_invoice, "reverse_charge_tax", 0) or 0), rate)
    is_rc = bool(getattr(purchase_invoice, "is_reverse_charge", False)) and rc > 0
    if skip_inventory_ap:
        # Stage 11 C2 — reverse only RC self-assess posted for GRN-linked invoices.
        if not is_rc:
            return None
        lines = [
            {"account_code": "2100", "debit": rc, "credit": 0, "description": "Tax payable reverse"},
            {"account_code": "1300", "debit": 0, "credit": rc, "description": "Input tax reverse"},
        ]
    elif is_rc:
        lines = [
            {"account_code": "2000", "debit": net, "credit": 0, "description": "AP reverse"},
            {"account_code": "2100", "debit": rc, "credit": 0, "description": "Tax payable reverse"},
            {"account_code": "1200", "debit": 0, "credit": net, "description": "Inventory reverse"},
            {"account_code": "1300", "debit": 0, "credit": rc, "description": "Input tax reverse"},
        ]
    else:
        total = to_base(float(purchase_invoice.total_amount), rate)
        tax = to_base(float(purchase_invoice.tax_amount or 0), rate)
        if tax > 0 and abs(total - (net + tax)) < 0.02:
            lines = [
                {"account_code": "2000", "debit": total, "credit": 0, "description": "AP reverse"},
                {"account_code": "1200", "debit": 0, "credit": net, "description": "Inventory reverse"},
                {"account_code": "1300", "debit": 0, "credit": tax, "description": "Input tax reverse"},
            ]
        else:
            lines = [
                {"account_code": "2000", "debit": total, "credit": 0, "description": "AP reverse"},
                {"account_code": "1200", "debit": 0, "credit": total, "description": "Inventory reverse"},
            ]
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Cancel purchase invoice {purchase_invoice.invoice_number}",
        reference=purchase_invoice.invoice_number,
        source_type="purchase_invoice_cancel",
        source_id=purchase_invoice.id,
        lines=lines,
    )


async def post_expense_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    expense: m.Expense,
) -> m.JournalEntry:
    await ensure_default_accounts(db, tenant_id)
    amount = float(expense.amount)
    liquid_code, liquid_label = await resolve_settlement_gl(
        db,
        tenant_id,
        expense.payment_method,
        liquid_account_id=getattr(expense, "liquid_account_id", None),
        outflow=True,
    )
    # Stage 14 E1 — debit mapped category COA when set; else Operating Expenses 6000
    debit_line: dict = {
        "account_code": "6000",
        "debit": amount,
        "credit": 0,
        "description": expense.category,
    }
    if getattr(expense, "category_id", None):
        cat = (
            await db.execute(
                select(m.ExpenseCategory).where(
                    m.ExpenseCategory.id == expense.category_id,
                    m.ExpenseCategory.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if cat and cat.account_id:
            mapped = (
                await db.execute(
                    select(m.Account).where(
                        m.Account.id == cat.account_id,
                        m.Account.tenant_id == tenant_id,
                        m.Account.is_active == True,  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
            if mapped and (mapped.account_type or "").strip().lower() == "expense":
                debit_line = {
                    "account_id": mapped.id,
                    "debit": amount,
                    "credit": 0,
                    "description": expense.category or mapped.name,
                }
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Expense {expense.category}",
        reference=expense.id,
        source_type="expense",
        source_id=expense.id,
        store_id=getattr(expense, "store_id", None),
        lines=[
            debit_line,
            {
                "account_code": liquid_code,
                "debit": 0,
                "credit": amount,
                "description": liquid_label,
            },
        ],
    )


async def post_pos_sale_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    tx: m.Transaction,
    payment_method: str = "cash",
    payments: list[dict] | None = None,
) -> m.JournalEntry:
    """Post POS sale GL; supports split tenders as multiple debit lines."""
    await ensure_default_accounts(db, tenant_id)
    amount = float(tx.total or 0)
    tax = float(tx.tax or 0)
    cart_discount = float((tx.payload or {}).get("discount_amount") or 0)
    # Net revenue: subtotal already excludes line discounts; cart discount reduces cash total.
    revenue = round(float(tx.subtotal or 0) - cart_discount, 2)
    if revenue < 0:
        raise HTTPException(status_code=400, detail="POS revenue after discount cannot be negative")
    if abs(amount - (revenue + tax)) > 0.02:
        raise HTTPException(status_code=400, detail="POS journal amounts do not balance")

    tenders = payments or [
        {"payment_method": payment_method, "amount": amount, "liquid_account_id": None}
    ]
    lines: list[dict] = []
    debit_sum = 0.0
    for tender in tenders:
        method = (tender.get("payment_method") or "cash").strip().lower()
        part = round(float(tender.get("amount") or 0), 2)
        if part <= 0:
            continue
        liquid_id = tender.get("liquid_account_id")
        if liquid_id and method != "credit":
            code, label = await resolve_settlement_gl(
                db, tenant_id, method, liquid_account_id=liquid_id, outflow=False
            )
        else:
            code, label = pos_debit_account_for_payment_method(method)
        lines.append(
            {
                "account_code": code,
                "debit": part,
                "credit": 0,
                "description": f"POS {tx.reference} ({label}/{method})",
            }
        )
        debit_sum += part
    if abs(debit_sum - amount) > 0.02:
        raise HTTPException(status_code=400, detail="POS tender debits do not equal sale total")

    lines.append(
        {"account_code": "4000", "debit": 0, "credit": revenue, "description": "Sales revenue"}
    )
    if tax > 0:
        lines.append(
            {"account_code": "2100", "debit": 0, "credit": tax, "description": "Tax payable"}
        )
    payload_items = list((tx.payload or {}).get("items") or [])
    cogs = await standard_cost_cogs_for_lines(db, tenant_id, payload_items)
    lines.extend(cogs_inventory_journal_lines(cogs))

    store_id = None
    if getattr(tx, "session_id", None):
        session = await db.get(m.PosSession, tx.session_id)
        if session and session.tenant_id == tenant_id:
            store_id = session.store_id
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"POS sale {tx.reference}",
        reference=tx.reference,
        source_type="pos_sale",
        source_id=tx.id,
        store_id=store_id,
        lines=lines,
    )


async def account_balances_through(
    db: AsyncSession,
    tenant_id: str,
    *,
    as_of: datetime | None = None,
    store_ids: list[str] | None = None,
) -> tuple[list[m.Account], dict[str, float]]:
    """Natural-side balances per account; as_of / store_ids rebuild from posted journals."""
    accounts = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id).order_by(m.Account.code)
        )
    ).scalars().all()
    if as_of is None and store_ids is None:
        return accounts, {a.id: float(a.balance or 0) for a in accounts}

    balances = {a.id: 0.0 for a in accounts}
    if store_ids is not None and len(store_ids) == 0:
        return accounts, balances

    stmt = (
        select(m.JournalEntryLine, m.Account)
        .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
        .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntry.tenant_id == tenant_id,
            m.JournalEntry.status == "posted",
        )
    )
    if as_of is not None:
        stmt = stmt.where(m.JournalEntry.entry_date <= as_of)
    if store_ids is not None:
        stmt = stmt.where(m.JournalEntry.store_id.in_(store_ids))
    for line, account in (await db.execute(stmt)).all():
        balances[account.id] = round(
            float(balances.get(account.id, 0.0))
            + _signed_balance_delta(
                account.account_type, float(line.debit or 0), float(line.credit or 0)
            ),
            2,
        )
    return accounts, balances


async def trial_balance(
    db: AsyncSession,
    tenant_id: str,
    *,
    as_of: datetime | None = None,
) -> dict:
    """Trial balance; optional as_of rebuilds balances from posted journals through that date."""
    accounts, bal_by_id = await account_balances_through(db, tenant_id, as_of=as_of)
    rows = []
    debit_total = 0.0
    credit_total = 0.0
    for account in accounts:
        bal = float(bal_by_id.get(account.id, 0.0))
        if account.account_type in {"asset", "expense"}:
            d, c = (bal, 0.0) if bal >= 0 else (0.0, abs(bal))
        else:
            d, c = (0.0, bal) if bal >= 0 else (abs(bal), 0.0)
        debit_total += d
        credit_total += c
        rows.append(
            {
                "account_id": account.id,
                "code": account.code,
                "name": account.name,
                "account_type": account.account_type,
                "debit": d,
                "credit": c,
                "balance": bal,
            }
        )
    as_of_date = (as_of or datetime.utcnow()).date().isoformat()
    return {
        "as_of": as_of_date,
        "rows": rows,
        "total_debit": round(debit_total, 2),
        "total_credit": round(credit_total, 2),
        "balanced": abs(debit_total - credit_total) < 0.01,
    }


def _pnl_bucket(account: m.Account) -> str:
    """Classify P&L account into revenue / cogs / operating_expense / other_income."""
    code = (account.code or "").strip()
    if account.account_type == "income":
        if code.startswith("42") or code.startswith("43"):
            return "other_income"
        return "revenue"
    if account.account_type == "expense":
        if code.startswith("5") or "cogs" in (account.name or "").lower():
            return "cogs"
        return "operating_expense"
    return "other"


async def profit_and_loss(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    branch_id: str | None = None,
) -> dict:
    """Period P&L from posted journal lines (optional date range / store / branch)."""
    await ensure_default_accounts(db, tenant_id)
    resolved_store, resolved_branch, store_ids = await resolve_journal_dimension_ids(
        db, tenant_id=tenant_id, store_id=store_id, branch_id=branch_id
    )

    stmt = (
        select(m.JournalEntryLine, m.Account, m.JournalEntry)
        .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
        .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntry.tenant_id == tenant_id,
            m.JournalEntry.status == "posted",
            m.Account.account_type.in_(("income", "expense")),
        )
    )
    if from_date:
        stmt = stmt.where(m.JournalEntry.entry_date >= from_date)
    if to_date:
        stmt = stmt.where(m.JournalEntry.entry_date <= to_date)
    if store_ids is not None:
        if store_ids:
            stmt = stmt.where(m.JournalEntry.store_id.in_(store_ids))
        else:
            stmt = stmt.where(m.JournalEntry.store_id.in_([]))

    rows = (await db.execute(stmt)).all()
    by_account: dict[str, dict] = {}
    for line, account, _entry in rows:
        debit = float(line.debit or 0)
        credit = float(line.credit or 0)
        # Income increases with credit; expense with debit.
        if account.account_type == "income":
            delta = credit - debit
        else:
            delta = debit - credit
        slot = by_account.get(account.id)
        if not slot:
            slot = {
                "account_id": account.id,
                "code": account.code,
                "name": account.name,
                "account_type": account.account_type,
                "bucket": _pnl_bucket(account),
                "balance": 0.0,
            }
            by_account[account.id] = slot
        slot["balance"] = round(float(slot["balance"]) + delta, 2)

    accounts_out = sorted(by_account.values(), key=lambda r: r["code"])
    revenue = round(sum(r["balance"] for r in accounts_out if r["bucket"] == "revenue"), 2)
    other_income = round(
        sum(r["balance"] for r in accounts_out if r["bucket"] == "other_income"), 2
    )
    cogs = round(sum(r["balance"] for r in accounts_out if r["bucket"] == "cogs"), 2)
    operating_expenses = round(
        sum(r["balance"] for r in accounts_out if r["bucket"] == "operating_expense"), 2
    )
    income = round(revenue + other_income, 2)
    expense = round(cogs + operating_expenses, 2)
    gross_profit = round(revenue - cogs, 2)
    net_profit = round(income - expense, 2)

    return {
        "from_date": from_date.date().isoformat() if from_date else None,
        "to_date": to_date.date().isoformat() if to_date else None,
        "store_id": resolved_store,
        "branch_id": resolved_branch,
        "revenue": revenue,
        "other_income": other_income,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "operating_expenses": operating_expenses,
        "income": income,
        "expense": expense,
        "net_profit": net_profit,
        "accounts": accounts_out,
    }
