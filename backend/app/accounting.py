"""Double-entry accounting helpers and auto-posting."""

from __future__ import annotations

from datetime import date, datetime, time

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
    ("3000", "Owner's Equity", "equity", False, False),
    ("4000", "Sales Revenue", "income", False, False),
    ("4100", "Sales Discounts", "expense", False, False),
    ("4200", "Purchase Discounts Taken", "income", False, False),
    ("4300", "FX Gain/Loss", "income", False, False),
    ("5000", "Cost of Goods Sold", "expense", False, False),
    ("6000", "Operating Expenses", "expense", False, False),
]


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


async def get_account_by_code(db: AsyncSession, tenant_id: str, code: str) -> m.Account:
    account = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id, m.Account.code == code)
        )
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=400, detail=f"Account code {code} not found for tenant")
    return account


async def ensure_default_accounts(db: AsyncSession, tenant_id: str) -> None:
    existing = {
        a.code: a
        for a in (
            await db.execute(select(m.Account).where(m.Account.tenant_id == tenant_id))
        ).scalars().all()
    }
    for code, name, account_type, is_cash, is_bank in DEFAULT_ACCOUNTS:
        if code not in existing:
            db.add(
                m.Account(
                    tenant_id=tenant_id,
                    code=code,
                    name=name,
                    account_type=account_type,
                    balance=0,
                    is_cash_account=is_cash,
                    is_bank_account=is_bank,
                )
            )
        else:
            row = existing[code]
            # Keep flags aligned for seeded liquid accounts without clobbering custom flags on others
            if code == "1000":
                row.is_cash_account = True
            if code == "1010":
                row.is_bank_account = True
    await db.flush()


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


def is_manual_journal(entry: m.JournalEntry) -> bool:
    st = (entry.source_type or "").strip().lower()
    return st in {"", "manual"}


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
) -> m.JournalEntry:
    """Reverse a posted manual journal within the current fiscal period (BR-10.2)."""
    entry = await get_journal_entry(db, tenant_id, entry_id)
    if entry.status != "posted":
        raise HTTPException(status_code=400, detail="Only posted journal entries can be unposted")
    if not is_manual_journal(entry):
        raise HTTPException(
            status_code=400,
            detail="Only manual journal entries can be unposted; reverse the source document instead",
        )

    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not in_current_fiscal_period(entry.entry_date, tenant.fiscal_year_start):
        raise HTTPException(
            status_code=400,
            detail="Unpost is only allowed within the current fiscal period",
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
        account.balance = float(account.balance or 0) - _signed_balance_delta(
            account.account_type, float(line.debit or 0), float(line.credit or 0)
        )

    entry.status = "unposted"
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="journal_unposted",
            entity="journal_entry",
            entity_id=entry.id,
            details={
                "entry_number": entry.entry_number,
                "total_debit": float(entry.total_debit or 0),
                "total_credit": float(entry.total_credit or 0),
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

    total_debit = sum(x["debit"] for x in normalized)
    total_credit = sum(x["credit"] for x in normalized)

    entry = m.JournalEntry(
        tenant_id=tenant_id,
        entry_number=f"JE-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        reference=reference,
        description=description,
        source_type=source_type,
        source_id=source_id,
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
        else:
            account = await get_account_by_code(db, tenant_id, line["account_code"])
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        db.add(
            m.JournalEntryLine(
                tenant_id=tenant_id,
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

    db.add(
        m.AuditLog(
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
    return {
        "id": entry.id,
        "entry_number": entry.entry_number,
        "entry_date": entry.entry_date,
        "reference": entry.reference,
        "description": entry.description,
        "source_type": entry.source_type,
        "source_id": entry.source_id,
        "total_debit": float(entry.total_debit),
        "total_credit": float(entry.total_credit),
        "status": entry.status,
        "attachment_url": entry.attachment_url,
        "has_attachment": bool(entry.attachment_url),
        "can_unpost": entry.status == "posted" and is_manual_journal(entry),
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
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Sales invoice {invoice.invoice_number}",
        reference=invoice.invoice_number,
        source_type="sales_invoice",
        source_id=invoice.id,
        lines=lines,
    )


async def post_sales_return_journal(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    sales_return: m.SalesReturn,
) -> m.JournalEntry:
    await ensure_default_accounts(db, tenant_id)
    revenue = float(sales_return.subtotal or 0)
    tax = float(sales_return.tax_amount or 0)
    total = float(sales_return.total_amount)
    cn = getattr(sales_return, "credit_note_number", None) or sales_return.return_number
    lines = [
        {"account_code": "4000", "debit": max(revenue, 0), "credit": 0, "description": "Sales return"},
        {"account_code": "1100", "debit": 0, "credit": total, "description": "AR credit"},
    ]
    if tax > 0:
        lines.append({"account_code": "2100", "debit": tax, "credit": 0, "description": "Tax reverse"})
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Sales return {sales_return.return_number} / {cn}",
        reference=cn,
        source_type="sales_return",
        source_id=sales_return.id,
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
    amount = round(float(amount), 2)
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
) -> m.JournalEntry:
    """Manual purchase bill: Dr Inventory (+ Input Tax if RC) / Cr AP (+ Tax Payable if RC)."""
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
    if is_rc:
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
) -> m.JournalEntry:
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
    if is_rc:
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
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"Expense {expense.category}",
        reference=expense.id,
        source_type="expense",
        source_id=expense.id,
        lines=[
            {"account_code": "6000", "debit": amount, "credit": 0, "description": expense.category},
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
    revenue = round(amount - tax, 2)
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
    return await post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=f"POS sale {tx.reference}",
        reference=tx.reference,
        source_type="pos_sale",
        source_id=tx.id,
        lines=lines,
    )


async def trial_balance(db: AsyncSession, tenant_id: str) -> dict:
    accounts = (
        await db.execute(
            select(m.Account).where(m.Account.tenant_id == tenant_id).order_by(m.Account.code)
        )
    ).scalars().all()
    rows = []
    debit_total = 0.0
    credit_total = 0.0
    for account in accounts:
        bal = float(account.balance or 0)
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
    return {
        "rows": rows,
        "total_debit": debit_total,
        "total_credit": credit_total,
        "balanced": abs(debit_total - credit_total) < 0.01,
    }


async def profit_and_loss(db: AsyncSession, tenant_id: str) -> dict:
    accounts = (
        await db.execute(select(m.Account).where(m.Account.tenant_id == tenant_id))
    ).scalars().all()
    income = sum(float(a.balance or 0) for a in accounts if a.account_type == "income")
    expense = sum(float(a.balance or 0) for a in accounts if a.account_type == "expense")
    return {
        "income": income,
        "expense": expense,
        "net_profit": income - expense,
        "accounts": [
            {
                "code": a.code,
                "name": a.name,
                "account_type": a.account_type,
                "balance": float(a.balance or 0),
            }
            for a in accounts
            if a.account_type in {"income", "expense"}
        ],
    }
