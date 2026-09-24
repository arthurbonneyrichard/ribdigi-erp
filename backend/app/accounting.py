"""Double-entry accounting helpers and auto-posting."""

from __future__ import annotations

from datetime import date, datetime, time

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import schema_compat
from app.doc_numbers import next_journal_entry_number
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

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
    ("3000", "Owner's Equity", "equity", False, False),
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
    debit = sum(money_json(x.get("debit") or 0) for x in lines)
    credit = sum(money_json(x.get("credit") or 0) for x in lines)
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
    company_id: str | None = None,
) -> tuple[str, str]:
    """Resolve (account_code, label), honoring optional per-payment liquid account override."""
    from app.workspace import assert_fk_company

    await ensure_default_accounts(db, tenant_id, company_id=company_id)
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
        assert_fk_company(account, company_id, detail="Settlement account not found")
        if not _account_is_settlement_eligible(account, outflow=outflow):
            raise HTTPException(
                status_code=400,
                detail="Account is not a cash/bank/settlement account for this payment direction",
            )
        return account.code, account.name
    if outflow:
        return supplier_payment_credit_gl(payment_method)
    return liquid_gl_for_payment_method(payment_method)


def require_account_code(value: str | None) -> str:
    """OpenAPI AccountCodeValue → 422; service defense-in-depth → 400.

    Used by journal lines + COA opening balances that resolve by ``account_code``
    (was strip-then-404/400 “not found” for malformed codes).
    """
    from app.schemas import validate_account_code_value

    try:
        return validate_account_code_value((value or "").strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def get_account_by_code(db: AsyncSession, tenant_id: str, code: str) -> m.Account:
    # OpenAPI AccountCodeValue → 422; service defense-in-depth → 400.
    code = require_account_code(code)
    account = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == code)
        )
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=400, detail=f"Account code {code} not found for tenant")
    return account


def assert_account_active(account: m.Account) -> None:
    """Block new postings/assignments against soft-deactivated COA rows (BR-10.1)."""
    if getattr(account, "is_active", True) is False:
        raise HTTPException(
            status_code=400,
            detail=f"Account {account.code} is inactive",
        )


async def ensure_default_accounts(db: AsyncSession, tenant_id: str) -> None:
    existing_codes = await schema_compat.existing_codes(db, "accounts", tenant_id)
    for code, name, account_type, is_cash, is_bank in DEFAULT_ACCOUNTS:
        if code in existing_codes:
            continue
        await schema_compat.insert_matching_row(
            db,
            "accounts",
            {
                "tenant_id": tenant_id,
                "code": code,
                "name": name,
                "account_type": account_type,
                "balance": 0,
                "opening_balance": 0,
                "is_cash_account": is_cash,
                "is_bank_account": is_bank,
                "is_system": True,
                "is_active": True,
                "parent_id": None,
                "company_id": None,
            },
        )
    await db.flush()


def serialize_coa_account(account: m.Account) -> dict:
    return {
        "id": account.id,
        "company_id": getattr(account, "company_id", None),
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
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    *,
    company_id: str | None = None,
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
    if company_id and row.company_id and row.company_id != company_id:
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
    company_id: str | None = None,
) -> dict:
    """Ledger drill-down for one COA account (Stage 8 A1)."""
    account = await get_tenant_account(db, tenant_id, account_id, company_id=company_id)
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
    company_id: str | None = None,
) -> None:
    if not parent_id:
        return
    if self_id and parent_id == self_id:
        raise HTTPException(status_code=400, detail="Account cannot be its own parent")
    parent = await get_tenant_account(db, tenant_id, parent_id, company_id=company_id)
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
        db,
        tenant_id=tenant_id,
        account_type=type_norm,
        parent_id=parent_id,
        company_id=company_id,
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
    company_id: str | None = None,
) -> m.Account:
    row = await get_tenant_account(db, tenant_id, account_id, company_id=company_id)
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
        dup_q = select(m.Account).where(
            m.Account.tenant_id == tenant_id,
            m.Account.code == code_norm,
            m.Account.id != row.id,
        )
        scope_cid = company_id or getattr(row, "company_id", None)
        if scope_cid:
            dup_q = dup_q.where(m.Account.company_id == scope_cid)
        dup = (await db.execute(dup_q)).scalar_one_or_none()
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
            company_id=company_id or getattr(row, "company_id", None),
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
    company_id: str | None = None,
) -> m.JournalEntry:
    """Post a balanced opening-balance journal for one account (BR-10.1)."""
    await ensure_default_accounts(db, tenant_id, company_id=company_id)
    account = await get_tenant_account(db, tenant_id, account_id, company_id=company_id)
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

    equity = await get_account_by_code(
        db, tenant_id, OPENING_BALANCE_EQUITY_CODE, company_id=company_id
    )
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
        company_id=company_id,
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
    company_id: str | None = None,
) -> m.Account:
    await ensure_default_accounts(db, tenant_id, company_id=company_id)
    kind_norm = (kind or "").strip().lower()
    if kind_norm not in {"cash", "bank"}:
        raise HTTPException(status_code=400, detail="kind must be cash or bank")
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

    is_cash = kind_norm == "cash"
    is_bank = kind_norm == "bank"
    if is_bank and not (bank_name or "").strip():
        raise HTTPException(status_code=400, detail="bank_name is required for bank accounts")

    row = m.Account(
        tenant_id=tenant_id,
        company_id=company_id,
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
    company_id: str | None = None,
) -> m.Account:
    from app.bank_recon import get_liquid_account

    row = await get_liquid_account(db, tenant_id, account_id, company_id=company_id)
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
    company_id: str | None = None,
) -> m.JournalEntry:
    """Move funds between cash/bank accounts (deposit, withdrawal, or transfer)."""
    from app.bank_recon import get_liquid_account

    await ensure_default_accounts(db, tenant_id, company_id=company_id)
    amt = round(float(amount), 2)
    if amt <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    if from_account_id == to_account_id:
        raise HTTPException(status_code=400, detail="from_account_id and to_account_id must differ")

    from_acct = await get_liquid_account(
        db, tenant_id, from_account_id, company_id=company_id
    )
    to_acct = await get_liquid_account(db, tenant_id, to_account_id, company_id=company_id)

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
        company_id=company_id,
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


def parse_fiscal_mmdd(value: str | None) -> tuple[int, int]:
    raw = (value or "01-01").strip()
    parts = raw.split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="fiscal_year_start must be MM-DD")
    try:
        mm, dd = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="fiscal_year_start must be MM-DD") from exc
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        raise HTTPException(status_code=400, detail="fiscal_year_start must be MM-DD")
    return mm, dd


def _safe_calendar_date(year: int, mm: int, dd: int) -> date:
    while dd >= 1:
        try:
            return date(year, mm, dd)
        except ValueError:
            dd -= 1
    raise HTTPException(status_code=400, detail="Invalid fiscal_year_start")


def fiscal_period_bounds(
    fiscal_year_start: str | None, *, as_of: date | None = None
) -> tuple[datetime, datetime]:
    """Return [start, end) datetime bounds for the fiscal period containing as_of."""
    as_of = as_of or datetime.utcnow().date()
    mm, dd = parse_fiscal_mmdd(fiscal_year_start)
    start_this_year = _safe_calendar_date(as_of.year, mm, dd)
    if as_of >= start_this_year:
        start = start_this_year
        end = _safe_calendar_date(as_of.year + 1, mm, dd)
    else:
        start = _safe_calendar_date(as_of.year - 1, mm, dd)
        end = start_this_year
    return datetime.combine(start, time.min), datetime.combine(end, time.min)


def in_current_fiscal_period(
    entry_date: datetime | date,
    fiscal_year_start: str | None,
    *,
    as_of: date | None = None,
) -> bool:
    start, end = fiscal_period_bounds(fiscal_year_start, as_of=as_of)
    if isinstance(entry_date, datetime):
        ed = entry_date
    else:
        ed = datetime.combine(entry_date, time.min)
    return start <= ed < end


def as_calendar_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def is_date_closed(entry_date: datetime | date, books_closed_through: date | datetime | None) -> bool:
    """True when entry_date falls on or before the inclusive books-closed date."""
    closed = as_calendar_date(books_closed_through)
    if closed is None:
        return False
    ed = as_calendar_date(entry_date)
    assert ed is not None
    return ed <= closed


async def get_tenant_or_404(db: AsyncSession, tenant_id: str) -> m.Tenant:
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


async def assert_books_open(
    db: AsyncSession,
    tenant_id: str,
    entry_date: datetime | date,
    *,
    action: str = "post",
    tenant: m.Tenant | None = None,
) -> None:
    """Reject mutations dated on or before tenants.books_closed_through (BR-10.2)."""
    row = tenant or await get_tenant_or_404(db, tenant_id)
    if is_date_closed(entry_date, row.books_closed_through):
        closed = as_calendar_date(row.books_closed_through)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Books are closed through {closed.isoformat()}; "
                f"cannot {action} journal entries on or before that date"
            ),
        )


def is_manual_journal(entry: m.JournalEntry) -> bool:
    st = (entry.source_type or "").strip().lower()
    return st in {"", "manual"}


def journal_can_unpost(entry: m.JournalEntry, tenant: m.Tenant | None) -> bool:
    if entry.status != "posted" or not is_manual_journal(entry):
        return False
    if tenant is None:
        return True
    if not in_current_fiscal_period(entry.entry_date, tenant.fiscal_year_start):
        return False
    if is_date_closed(entry.entry_date, tenant.books_closed_through):
        return False
    return True


async def get_journal_entry(
    db: AsyncSession, tenant_id: str, entry_id: str
) -> m.JournalEntry:
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
    return entry


async def unpost_journal_entry(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    entry_id: str,
    reason: str | None = None,
) -> m.JournalEntry:
    """Reverse a posted manual journal within the current fiscal period (BR-10.2)."""
    reason_s = require_honest_narrative(reason, label="unpost reason")

    entry = await get_journal_entry(db, tenant_id, entry_id)
    if entry.status != "posted":
        raise HTTPException(status_code=400, detail="Only posted journal entries can be unposted")
    if not is_manual_journal(entry):
        raise HTTPException(
            status_code=400,
            detail="Only manual journal entries can be unposted; reverse the source document instead",
        )

    tenant = await get_tenant_or_404(db, tenant_id)
    if not in_current_fiscal_period(entry.entry_date, tenant.fiscal_year_start):
        raise HTTPException(
            status_code=400,
            detail="Unpost is only allowed within the current fiscal period",
        )
    await assert_books_open(
        db, tenant_id, entry.entry_date, action="unpost", tenant=tenant
    )

    lines = (
        await db.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.tenant_id == tenant_id,
                m.JournalEntryLine.journal_entry_id == entry.id,
            )
        )
    ).scalars().all()
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
            raise HTTPException(status_code=404, detail="Account not found for journal line")
        account.balance = money_json(account.balance or 0) - _signed_balance_delta(
            account.account_type, money_json(line.debit or 0), money_json(line.credit or 0)
        )

    entry.status = "unposted"
    entry.description = ((entry.description or "") + f"\nUnpost: {reason_s}").strip()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="journal_unposted",
            entity="journal_entry",
            entity_id=entry.id,
            details={
                "entry_number": entry.entry_number,
                "total_debit": money_json(entry.total_debit or 0),
                "total_credit": money_json(entry.total_credit or 0),
                "reason": reason_s,
            },
        )
    )
    return entry


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
    entry_date: datetime | date | None = None,
) -> m.JournalEntry:
    if len(lines) < 2:
        raise HTTPException(status_code=400, detail="Journal entry requires at least two lines")

    when = entry_date or datetime.utcnow()
    await assert_books_open(db, tenant_id, when, action="post")

    normalized = []
    for line in lines:
        debit = money_json(line.get("debit") or 0)
        credit = money_json(line.get("credit") or 0)
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

    # OpenAPI JournalDescriptionValue → 422; service defense-in-depth → 400.
    description = require_honest_narrative(
        description, label="journal description", min_length=2
    )
    for line in normalized:
        line["description"] = optional_honest_narrative(
            line.get("description"), label="journal line description"
        )
    # OpenAPI JournalReferenceValue → 422; service defense-in-depth → 400.
    reference = optional_honest_narrative(
        reference, label="journal reference", max_length=100
    )

    total_debit = sum(x["debit"] for x in normalized)
    total_credit = sum(x["credit"] for x in normalized)
    resolved_store = await resolve_journal_store_id(
        db, tenant_id=tenant_id, store_id=store_id, company_id=company_id
    )

    if isinstance(when, date) and not isinstance(when, datetime):
        when_dt = datetime.combine(when, time.min)
    else:
        when_dt = when  # type: ignore[assignment]

    entry = m.JournalEntry(
        tenant_id=tenant_id,
        entry_number=await next_journal_entry_number(db, tenant_id),
        entry_date=when_dt,
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
        assert_account_active(account)

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
        account.balance = money_json(account.balance or 0) + _signed_balance_delta(
            account.account_type, line["debit"], line["credit"]
        )

    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="journal_posted",
            entity="journal_entry",
            entity_id=entry.id,
            details={
                "entry_number": entry.entry_number,
                "total_debit": money_json(total_debit),
                "source_type": source_type,
                "source_id": source_id,
            },
        )
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
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == entry.tenant_id))
    ).scalar_one_or_none()
    return {
        "id": entry.id,
        "company_id": getattr(entry, "company_id", None),
        "entry_number": entry.entry_number,
        "entry_date": entry.entry_date,
        "reference": entry.reference,
        "description": entry.description,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "total_debit": money_json(entry.total_debit),
        "total_credit": money_json(entry.total_credit),
        "status": entry.status,
        "attachment_url": entry.attachment_url,
        "has_attachment": bool(entry.attachment_url),
        "can_unpost": journal_can_unpost(entry, tenant),
        "created_at": entry.created_at,
        "balanced": abs(money_json(entry.total_debit) - money_json(entry.total_credit)) < 0.01,
        "lines": [
            {
                "id": ln.id,
                "company_id": getattr(ln, "company_id", None),
                "account_id": ln.account_id,
                "debit": money_json(ln.debit),
                "credit": money_json(ln.credit),
                "description": ln.description,
            }
            for ln in lines
        ],
    }


async def period_status(db: AsyncSession, tenant_id: str) -> dict:
    """Fiscal year bounds + books-closed-through for Accounting UI (BR-10.2)."""
    tenant = await get_tenant_or_404(db, tenant_id)
    start, end = fiscal_period_bounds(tenant.fiscal_year_start)
    closed = as_calendar_date(tenant.books_closed_through)
    return {
        "fiscal_year_start": tenant.fiscal_year_start or "01-01",
        "current_fiscal_start": start.date().isoformat(),
        "current_fiscal_end_exclusive": end.date().isoformat(),
        "books_closed_through": closed.isoformat() if closed else None,
        "books_are_closed": closed is not None,
    }


async def close_books(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    through_date: date,
    reason: str | None = None,
) -> dict:
    """Advance tenants.books_closed_through (inclusive). Cannot close future dates."""
    reason_s = require_honest_narrative(reason, label="close reason")
    tenant = await get_tenant_or_404(db, tenant_id)
    today = datetime.utcnow().date()
    if through_date > today:
        raise HTTPException(
            status_code=400,
            detail="Cannot close books through a future date",
        )
    current = as_calendar_date(tenant.books_closed_through)
    if current is not None and through_date < current:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Books are already closed through {current.isoformat()}; "
                "use reopen to move the closed date earlier"
            ),
        )
    tenant.books_closed_through = through_date
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="period_closed",
            entity="tenant",
            entity_id=tenant_id,
            details={
                "books_closed_through": through_date.isoformat(),
                "previous": current.isoformat() if current else None,
                "reason": reason_s,
            },
        )
    )
    return await period_status(db, tenant_id)


async def reopen_books(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    through_date: date | None,
    reason: str | None = None,
) -> dict:
    """Move books_closed_through earlier, or clear when through_date is null."""
    reason_s = require_honest_narrative(reason, label="reopen reason")
    tenant = await get_tenant_or_404(db, tenant_id)
    current = as_calendar_date(tenant.books_closed_through)
    if current is None:
        raise HTTPException(status_code=400, detail="Books are not closed")
    if through_date is not None:
        if through_date >= current:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Reopen through_date must be before current closed date "
                    f"({current.isoformat()}), or omit to clear"
                ),
            )
        if through_date > datetime.utcnow().date():
            raise HTTPException(
                status_code=400,
                detail="Cannot set books_closed_through to a future date",
            )
    previous = current.isoformat()
    tenant.books_closed_through = through_date
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="period_reopened",
            entity="tenant",
            entity_id=tenant_id,
            details={
                "books_closed_through": through_date.isoformat() if through_date else None,
                "previous": previous,
                "reason": reason_s,
            },
        )
    )
    return await period_status(db, tenant_id)


async def unit_cost_for_line(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    variant_id: str | None = None,
) -> float:
    """Standard unit cost: variant.cost_price if set, else product.cost_price."""
    if variant_id:
        variant = (
            await db.execute(
                select(m.ProductVariant).where(
                    m.ProductVariant.id == variant_id,
                    m.ProductVariant.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if variant is not None:
            v_cost = money_json(variant.cost_price or 0)
            if v_cost > 0:
                return v_cost
    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == product_id,
                m.Product.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not product:
        return 0.0
    return money_json(product.cost_price or 0)


async def stock_qty_for_cogs(
    db: AsyncSession,
    *,
    tenant_id: str,
    product_id: str,
    quantity: float,
    unit_id: str | None = None,
) -> float:
    """Convert line qty to stockkeeping units for COGS (matches stock_out)."""
    from app.uom import to_stock_qty

    product = (
        await db.execute(
            select(m.Product).where(
                m.Product.id == product_id,
                m.Product.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not product:
        return money_json(quantity or 0)
    qty_base, _, _ = await to_stock_qty(
        db,
        tenant_id=tenant_id,
        quantity=money_json(quantity),
        from_unit_id=unit_id,
        product=product,
    )
    return money_json(qty_base)


async def compute_standard_cogs(
    db: AsyncSession,
    *,
    tenant_id: str,
    lines: list[dict],
) -> float:
    """Sum qty×standard cost for COGS lines.

    Each line: product_id, quantity, optional unit_id / variant_id.
    """
    total = 0.0
    for line in lines:
        product_id = line.get("product_id")
        if not product_id:
            continue
        qty = money_json(line.get("quantity") or 0)
        if qty <= 0:
            continue
        unit_id = line.get("unit_id")
        try:
            stock_qty = await stock_qty_for_cogs(
                db,
                tenant_id=tenant_id,
                product_id=product_id,
                quantity=qty,
                unit_id=unit_id,
            )
        except HTTPException:
            stock_qty = qty
        cost = await unit_cost_for_line(
            db,
            tenant_id=tenant_id,
            product_id=product_id,
            variant_id=line.get("variant_id"),
        )
        total += stock_qty * cost
    return money_json(round(total, 2))


def append_cogs_lines(lines: list[dict], cogs: float, *, reverse: bool = False) -> None:
    """Append Dr 5000 / Cr 1200 (or reverse) when cogs > 0."""
    cogs = money_json(round(money_json(cogs or 0), 2))
    if cogs <= 0:
        return
    if reverse:
        lines.append(
            {
                "account_code": "1200",
                "debit": cogs,
                "credit": 0,
                "description": "Inventory restock (COGS reverse)",
            }
        )
        lines.append(
            {
                "account_code": "5000",
                "debit": 0,
                "credit": cogs,
                "description": "COGS reverse",
            }
        )
    else:
        lines.append(
            {
                "account_code": "5000",
                "debit": cogs,
                "credit": 0,
                "description": "Cost of goods sold",
            }
        )
        lines.append(
            {
                "account_code": "1200",
                "debit": 0,
                "credit": cogs,
                "description": "Inventory relief",
            }
        )


async def post_sales_invoice_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice: m.SalesInvoice,
) -> m.JournalEntry:
    await ensure_default_accounts(db, tenant_id)
    from app.fx import doc_rate, to_base
    from app.sales import list_invoice_items

    rate = doc_rate(invoice)
    revenue = to_base(
        money_json(invoice.subtotal) - money_json(invoice.discount_amount or 0), rate
    )
    tax = to_base(money_json(invoice.tax_amount or 0), rate)
    total = to_base(money_json(invoice.total_amount), rate)
    lines = [
        {"account_code": "1100", "debit": total, "credit": 0, "description": "AR"},
        {"account_code": "4000", "debit": 0, "credit": max(revenue, 0), "description": "Sales"},
    ]
    if tax > 0:
        lines.append({"account_code": "2100", "debit": 0, "credit": tax, "description": "Tax"})
    if revenue < 0:
        raise HTTPException(status_code=400, detail="Invoice revenue after discount cannot be negative")

    items = await list_invoice_items(db, tenant_id, invoice.id)
    cogs = await compute_standard_cogs(
        db,
        tenant_id=tenant_id,
        lines=[
            {
                "product_id": it.product_id,
                "quantity": money_json(it.quantity),
                "unit_id": it.unit_id,
                "variant_id": it.variant_id,
            }
            for it in items
        ],
    )
    # COGS is in base currency terms (cost_price is tenant base)
    append_cogs_lines(lines, cogs, reverse=False)

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
    from app.sales_docs import list_return_items

    revenue = money_json(sales_return.subtotal or 0)
    tax = money_json(sales_return.tax_amount or 0)
    total = money_json(sales_return.total_amount)
    cn = getattr(sales_return, "credit_note_number", None) or sales_return.return_number
    lines = [
        {"account_code": "4000", "debit": max(revenue, 0), "credit": 0, "description": "Sales return"},
        {"account_code": "1100", "debit": 0, "credit": total, "description": "AR credit"},
    ]
    if tax > 0:
        lines.append({"account_code": "2100", "debit": tax, "credit": 0, "description": "Tax reverse"})

    # Reverse COGS only for restocked sellable lines (matches stock_in path)
    if sales_return.restock:
        items = await list_return_items(db, tenant_id, sales_return.id)
        cogs = await compute_standard_cogs(
            db,
            tenant_id=tenant_id,
            lines=[
                {
                    "product_id": it.product_id,
                    "quantity": money_json(it.quantity),
                    "variant_id": it.variant_id,
                }
                for it in items
                if (it.condition or "sellable") == "sellable"
            ],
        )
        append_cogs_lines(lines, cogs, reverse=True)

    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Sales return {sales_return.return_number} / {cn}",
        reference=cn,
        source_type="sales_return",
        source_id=sales_return.id,
        store_id=getattr(invoice, "store_id", None) if invoice is not None else None,
        lines=lines,
    )


async def post_sales_return_refund_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    sales_return: m.SalesReturn,
    amount: float,
    payment_method: str = "cash",
    liquid_account_id: str | None = None,
) -> m.JournalEntry:
    """Pay out customer credit from a return: Dr AR, Cr cash/bank."""
    await ensure_default_accounts(db, tenant_id)
    amount = money_json(round(money_json(amount), 2))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Refund amount must be positive")
    liquid_code, liquid_label = await resolve_settlement_gl(
        db,
        tenant_id,
        payment_method,
        liquid_account_id=liquid_account_id,
        outflow=True,
    )
    cn = getattr(sales_return, "credit_note_number", None) or sales_return.return_number
    lines = [
        {"account_code": "1100", "debit": amount, "credit": 0, "description": "Clear AR credit for refund"},
        {
            "account_code": liquid_code,
            "debit": 0,
            "credit": amount,
            "description": f"Customer refund via {liquid_label}",
        },
    ]
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Refund for return {sales_return.return_number} / {cn}",
        reference=cn,
        source_type="sales_return_refund",
        source_id=sales_return.id,
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

    amount = money_json(payment.amount)
    discount = money_json(getattr(payment, "early_payment_discount", 0) or 0)
    pay_rate = doc_rate(payment)
    liquid_code, liquid_label = await resolve_settlement_gl(
        db,
        tenant_id,
        payment.payment_method,
        liquid_account_id=getattr(payment, "liquid_account_id", None),
        outflow=False,
        company_id=getattr(payment, "company_id", None),
    )

    cash_base = to_base(amount, pay_rate)
    if allocations:
        ar_base = 0.0
        disc_base = 0.0
        cash_at_inv = 0.0
        for inv, settle, disc in allocations:
            inv_rate = doc_rate(inv)
            cash_doc = money_json(round(settle - disc, 2))
            ar_base = money_json(round(ar_base + to_base(settle, inv_rate), 2))
            disc_base = money_json(round(disc_base + to_base(disc, inv_rate), 2))
            cash_at_inv = money_json(round(cash_at_inv + to_base(cash_doc, inv_rate), 2))
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

    payment.fx_gain_loss = money_json(round(fx_amt, 2))
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

    amount = money_json(payment.amount)
    discount = money_json(getattr(payment, "early_payment_discount", 0) or 0)
    pay_rate = doc_rate(payment)
    liquid_code, liquid_label = await resolve_settlement_gl(
        db,
        tenant_id,
        payment.payment_method,
        liquid_account_id=getattr(payment, "liquid_account_id", None),
        outflow=True,
        company_id=getattr(payment, "company_id", None),
    )
    cash_base = to_base(amount, pay_rate)
    if allocations:
        ap_base = 0.0
        disc_base = 0.0
        for inv, settle, disc in allocations:
            inv_rate = doc_rate(inv)
            ap_base = money_json(round(ap_base + to_base(settle, inv_rate), 2))
            disc_base = money_json(round(disc_base + to_base(disc, inv_rate), 2))
        fx_amt, fx_extra = fx_lines_for_payment(
            cash_base=cash_base, ap_base=ap_base, discount_base=disc_base
        )
    else:
        ap_base = to_base(amount + discount, pay_rate)
        disc_base = to_base(discount, pay_rate)
        fx_amt, fx_extra = 0.0, []

    payment.fx_gain_loss = money_json(round(fx_amt, 2))
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


async def post_opening_stock_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    entry_id: str,
    reference: str,
    inventory_value: float,
    description: str | None = None,
) -> m.JournalEntry | None:
    """Dr Inventory 1200 / Cr Owner's Equity 3000 for opening stock at cost."""
    if inventory_value <= 0:
        return None
    await ensure_default_accounts(db, tenant_id)
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description or f"Opening stock {reference}",
        reference=reference,
        source_type="opening_stock",
        source_id=entry_id,
        lines=[
            {"account_code": "1200", "debit": inventory_value, "credit": 0, "description": "Opening inventory"},
            {"account_code": "3000", "debit": 0, "credit": inventory_value, "description": "Opening equity"},
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
    total = money_json(purchase_return.total_amount)
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
        money_json(round(
            money_json(purchase_invoice.subtotal or 0)
            - money_json(purchase_invoice.discount_amount or 0),
            2,
        )),
        rate,
    )
    rc = to_base(
        money_json(getattr(purchase_invoice, "reverse_charge_tax", 0) or 0), rate
    )
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
        total = to_base(money_json(purchase_invoice.total_amount), rate)
        tax = to_base(money_json(purchase_invoice.tax_amount or 0), rate)
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
        money_json(round(
            money_json(purchase_invoice.subtotal or 0)
            - money_json(purchase_invoice.discount_amount or 0),
            2,
        )),
        rate,
    )
    rc = to_base(
        money_json(getattr(purchase_invoice, "reverse_charge_tax", 0) or 0), rate
    )
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
        total = to_base(money_json(purchase_invoice.total_amount), rate)
        tax = to_base(money_json(purchase_invoice.tax_amount or 0), rate)
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
    amount = money_json(expense.amount)
    liquid_code, liquid_label = await resolve_settlement_gl(
        db,
        tenant_id,
        expense.payment_method,
        liquid_account_id=getattr(expense, "liquid_account_id", None),
        outflow=True,
        company_id=getattr(expense, "company_id", None),
    )
    debit_code = "6000"
    debit_desc = expense.category
    category_id = getattr(expense, "category_id", None)
    if category_id:
        cat = await db.get(m.ExpenseCategory, category_id)
        if cat and cat.tenant_id == tenant_id and getattr(cat, "account_id", None):
            account = await db.get(m.Account, cat.account_id)
            if (
                account
                and account.tenant_id == tenant_id
                and (account.account_type or "").lower() == "expense"
            ):
                debit_code = account.code
                debit_desc = f"{expense.category} ({account.code})"
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
            {
                "account_code": debit_code,
                "debit": amount,
                "credit": 0,
                "description": debit_desc,
            },
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
    amount = money_json(tx.total or 0)
    tax = money_json(tx.tax or 0)
    revenue = money_json(round(amount - tax, 2))
    if abs(amount - (revenue + tax)) > 0.02:
        raise HTTPException(status_code=400, detail="POS journal amounts do not balance")

    tenders = payments or [
        {"payment_method": payment_method, "amount": amount, "liquid_account_id": None}
    ]
    lines: list[dict] = []
    debit_sum = 0.0
    for tender in tenders:
        method = (tender.get("payment_method") or "cash").strip().lower()
        part = money_json(round(money_json(tender.get("amount") or 0), 2))
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

    payload = tx.payload if isinstance(tx.payload, dict) else {}
    pos_items = list(payload.get("items") or [])
    cogs = await compute_standard_cogs(
        db,
        tenant_id=tenant_id,
        lines=[
            {
                "product_id": it.get("product_id"),
                "quantity": money_json(it.get("quantity") or 0),
                "unit_id": it.get("unit_id"),
                "variant_id": it.get("variant_id"),
            }
            for it in pos_items
            if it.get("product_id")
        ],
    )
    append_cogs_lines(lines, cogs, reverse=False)

    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"POS sale {tx.reference}",
        reference=tx.reference,
        source_type="pos_sale",
        source_id=tx.id,
        store_id=store_id,
        company_id=cid,
        lines=lines,
    )


async def trial_balance(
    db: AsyncSession,
    tenant_id: str,
    *,
    as_of: datetime | None = None,
    store_id: str | None = None,
    branch_id: str | None = None,
) -> dict:
    """Trial balance (BR-10.6 / BR-14.5).

    - No ``as_of`` (and no location filter): live ``Account.balance`` (``mode=balances``).
    - With ``as_of``: reconstruct signed balances from posted journal lines
      through that timestamp (``mode=journals``), matching balance-sheet as-of.
    - Optional ``store_id`` / ``branch_id``: reconstruct from journals attributable to
      that location (forces ``mode=journals``; defaults ``as_of`` to end of today).
    """
    await ensure_default_accounts(db, tenant_id)
    accounts = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id).order_by(m.Account.code)
        )
    ).scalars().all()

    store_ids = await _pnl_store_ids(
        db, tenant_id, store_id=store_id, branch_id=branch_id
    )
    location_filter = store_ids is not None
    effective_as_of = as_of
    if location_filter and effective_as_of is None:
        today = datetime.utcnow().date()
        effective_as_of = datetime(
            today.year, today.month, today.day, 23, 59, 59, 999999
        )

    if effective_as_of is None:
        bal_by_id = {a.id: money_json(a.balance) for a in accounts}
        as_of_day = datetime.utcnow().date()
        mode = "balances"
    else:
        bal_by_id = {a.id: 0.0 for a in accounts}
        allowed_journal_ids: set[str] | None = None
        if location_filter:
            allowed_journal_ids = await _pnl_journal_ids_for_stores(
                db, tenant_id, store_ids or [], branch_id=branch_id
            )
        stmt = (
            select(m.JournalEntryLine, m.Account)
            .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
            .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
            .where(
                m.JournalEntryLine.tenant_id == tenant_id,
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.status == "posted",
                m.JournalEntry.entry_date <= effective_as_of,
                m.Account.tenant_id == tenant_id,
            )
        )
        if allowed_journal_ids is not None:
            if not allowed_journal_ids:
                stmt = stmt.where(m.JournalEntry.id.in_([]))
            else:
                stmt = stmt.where(m.JournalEntry.id.in_(allowed_journal_ids))
        for line, account in (await db.execute(stmt)).all():
            bal_by_id[account.id] = money_json(bal_by_id.get(account.id, 0)) + _signed_balance_delta(
                account.account_type,
                money_json(line.debit),
                money_json(line.credit),
            )
        as_of_day = effective_as_of.date()
        mode = "journals"

    rows = []
    debit_total = 0.0
    credit_total = 0.0
    for account in accounts:
        bal = money_json(round(money_json(bal_by_id.get(account.id, 0)), 2))
        if mode == "journals" and abs(bal) < 0.0001:
            continue
        if account.account_type in {"asset", "expense"}:
            d, c = (bal, 0.0) if bal >= 0 else (0.0, abs(bal))
        else:
            d, c = (0.0, bal) if bal >= 0 else (abs(bal), 0.0)
        d = money_json(d)
        c = money_json(c)
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
        "as_of": as_of_day.isoformat(),
        "mode": mode,
        "store_id": store_id,
        "branch_id": branch_id,
        "rows": rows,
        "total_debit": money_json(round(debit_total, 2)),
        "total_credit": money_json(round(credit_total, 2)),
        "balanced": abs(debit_total - credit_total) < 0.01,
    }


async def _pnl_store_ids(
    db: AsyncSession,
    tenant_id: str,
    *,
    store_id: str | None,
    branch_id: str | None,
) -> list[str] | None:
    """Resolve store ids for location-filtered P&L; None means no location filter."""
    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.id == store_id,
                    m.Store.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        if branch_id and store.branch_id != branch_id:
            raise HTTPException(
                status_code=400,
                detail="store_id is not in the requested branch",
            )
        return [store.id]
    if branch_id:
        branch = (
            await db.execute(
                select(m.Branch).where(
                    m.Branch.id == branch_id,
                    m.Branch.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        rows = (
            await db.execute(
                select(m.Store.id).where(
                    m.Store.tenant_id == tenant_id,
                    m.Store.branch_id == branch_id,
                )
            )
        ).scalars().all()
        return list(rows)
    return None


async def _pnl_journal_ids_for_stores(
    db: AsyncSession,
    tenant_id: str,
    store_ids: list[str],
    *,
    branch_id: str | None = None,
) -> set[str]:
    """Journal entries attributable to the given stores (sales/POS/expense/returns).

    When `branch_id` is set, also include expenses assigned directly to that branch
    (even when `store_id` is null).
    """
    if not store_ids and not branch_id:
        return set()

    inv_ids = set()
    if store_ids:
        inv_ids = set(
            (
                await db.execute(
                    select(m.SalesInvoice.id).where(
                        m.SalesInvoice.tenant_id == tenant_id,
                        m.SalesInvoice.store_id.in_(store_ids),
                    )
                )
            ).scalars().all()
        )
    exp_ids = set()
    if store_ids:
        exp_ids |= set(
            (
                await db.execute(
                    select(m.Expense.id).where(
                        m.Expense.tenant_id == tenant_id,
                        m.Expense.store_id.in_(store_ids),
                    )
                )
            ).scalars().all()
        )
    if branch_id:
        exp_ids |= set(
            (
                await db.execute(
                    select(m.Expense.id).where(
                        m.Expense.tenant_id == tenant_id,
                        m.Expense.branch_id == branch_id,
                    )
                )
            ).scalars().all()
        )
    tx_ids = set()
    return_ids = set()
    if store_ids:
        tx_ids = set(
            (
                await db.execute(
                    select(m.Transaction.id)
                    .join(m.PosSession, m.PosSession.id == m.Transaction.session_id)
                    .where(
                        m.Transaction.tenant_id == tenant_id,
                        m.PosSession.tenant_id == tenant_id,
                        m.PosSession.store_id.in_(store_ids),
                    )
                )
            ).scalars().all()
        )
        return_ids = set(
            (
                await db.execute(
                    select(m.SalesReturn.id)
                    .join(m.SalesInvoice, m.SalesInvoice.id == m.SalesReturn.sales_invoice_id)
                    .where(
                        m.SalesReturn.tenant_id == tenant_id,
                        m.SalesInvoice.tenant_id == tenant_id,
                        m.SalesInvoice.store_id.in_(store_ids),
                    )
                )
            ).scalars().all()
        )

    from sqlalchemy import or_

    clauses = []
    if inv_ids:
        clauses.append(
            (m.JournalEntry.source_type == "sales_invoice")
            & (m.JournalEntry.source_id.in_(inv_ids))
        )
    if tx_ids:
        clauses.append(
            (m.JournalEntry.source_type == "pos_sale")
            & (m.JournalEntry.source_id.in_(tx_ids))
        )
    if exp_ids:
        clauses.append(
            (m.JournalEntry.source_type == "expense")
            & (m.JournalEntry.source_id.in_(exp_ids))
        )
    if return_ids:
        clauses.append(
            (m.JournalEntry.source_type.in_(("sales_return", "sales_return_refund")))
            & (m.JournalEntry.source_id.in_(return_ids))
        )
    if not clauses:
        return set()

    rows = (
        await db.execute(
            select(m.JournalEntry.id).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.status == "posted",
                or_(*clauses),
            )
        )
    ).scalars().all()
    return set(rows)


def _pnl_pack(
    *,
    revenue: float,
    cogs: float,
    operating_expenses: float,
    accounts: list[dict],
    from_date: datetime | None,
    to_date: datetime | None,
    store_id: str | None,
    branch_id: str | None,
    mode: str,
) -> dict:
    expense = money_json(round(cogs + operating_expenses, 2))
    gross_profit = money_json(round(revenue - cogs, 2))
    net_profit = money_json(round(revenue - expense, 2))
    return {
        "income": money_json(round(money_json(revenue), 2)),  # back-compat alias
        "revenue": money_json(round(money_json(revenue), 2)),
        "cogs": money_json(round(money_json(cogs), 2)),
        "gross_profit": money_json(round(money_json(gross_profit), 2)),
        "operating_expenses": money_json(round(money_json(operating_expenses), 2)),
        "expense": money_json(round(money_json(expense), 2)),  # back-compat: total expenses incl. COGS
        "net_profit": money_json(round(money_json(net_profit), 2)),
        "accounts": accounts,
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "store_id": store_id,
        "branch_id": branch_id,
        "mode": mode,
    }


async def profit_and_loss(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    store_id: str | None = None,
    branch_id: str | None = None,
) -> dict:
    """P&L with revenue, COGS (5000), gross profit, and operating expenses (BR-10.6 / BR-14.5).

    Without filters: lifetime income/expense account balances (back-compat).
    With date and/or store/branch filters: posted journal-line activity. Location
    filters keep only sales_invoice / pos_sale / expense / sales_return journals
    attributable to the store(s); unattributable journals are excluded.
    """
    store_ids = await _pnl_store_ids(
        db, tenant_id, store_id=store_id, branch_id=branch_id
    )
    use_journals = bool(from_date or to_date or store_ids is not None)

    if not use_journals:
        accounts = (
            await db.execute(select(m.Account).where(m.Account.tenant_id == tenant_id))
        ).scalars().all()
        revenue = sum(money_json(a.balance) for a in accounts if a.account_type == "income")
        cogs = sum(money_json(a.balance) for a in accounts if a.code == "5000")
        operating_expenses = sum(
            money_json(a.balance)
            for a in accounts
            if a.account_type == "expense" and a.code != "5000"
        )
        return _pnl_pack(
            revenue=revenue,
            cogs=cogs,
            operating_expenses=operating_expenses,
            accounts=[
                {
                    "code": a.code,
                    "name": a.name,
                    "account_type": a.account_type,
                    "balance": money_json(a.balance),
                }
                for a in accounts
                if a.account_type in {"income", "expense"}
            ],
            from_date=None,
            to_date=None,
            store_id=None,
            branch_id=None,
            mode="balances",
        )

    stmt = (
        select(m.JournalEntryLine, m.JournalEntry, m.Account)
        .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
        .join(m.Account, m.Account.id == m.JournalEntryLine.account_id)
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntry.tenant_id == tenant_id,
            m.JournalEntry.status == "posted",
            m.Account.tenant_id == tenant_id,
            m.Account.account_type.in_(("income", "expense")),
        )
    )
    if from_date:
        stmt = stmt.where(m.JournalEntry.entry_date >= from_date)
    if to_date:
        stmt = stmt.where(m.JournalEntry.entry_date <= to_date)
    if store_ids is not None:
        je_ids = await _pnl_journal_ids_for_stores(
            db, tenant_id, store_ids, branch_id=branch_id
        )
        if not je_ids:
            return _pnl_pack(
                revenue=0,
                cogs=0,
                operating_expenses=0,
                accounts=[],
                from_date=from_date,
                to_date=to_date,
                store_id=store_id,
                branch_id=branch_id,
                mode="journals",
            )
        stmt = stmt.where(m.JournalEntry.id.in_(je_ids))

    rows = (await db.execute(stmt)).all()
    by_account: dict[str, dict] = {}
    revenue = 0.0
    cogs = 0.0
    operating_expenses = 0.0
    for line, _entry, account in rows:
        debit = money_json(line.debit)
        credit = money_json(line.credit)
        if account.account_type == "income":
            net = money_json(round(credit - debit, 2))
            revenue = money_json(round(revenue + net, 2))
        else:
            net = money_json(round(debit - credit, 2))
            if account.code == "5000":
                cogs = money_json(round(cogs + net, 2))
            else:
                operating_expenses = money_json(round(operating_expenses + net, 2))
        bucket = by_account.setdefault(
            account.id,
            {
                "code": account.code,
                "name": account.name,
                "account_type": account.account_type,
                "balance": 0.0,
            },
        )
        bucket["balance"] = money_json(round(money_json(bucket["balance"]) + net, 2))

    accounts_out = sorted(by_account.values(), key=lambda r: r["code"] or "")
    return _pnl_pack(
        revenue=revenue,
        cogs=cogs,
        operating_expenses=operating_expenses,
        accounts=accounts_out,
        from_date=from_date,
        to_date=to_date,
        store_id=store_id,
        branch_id=branch_id,
        mode="journals",
    )
