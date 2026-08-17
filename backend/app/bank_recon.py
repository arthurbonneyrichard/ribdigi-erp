"""Bank / cash statement reconciliation against journal lines."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m


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


def serialize_line(line: m.BankStatementLine) -> dict:
    return {
        "id": line.id,
        "statement_id": line.statement_id,
        "txn_date": line.txn_date,
        "amount": float(line.amount),
        "description": line.description,
        "external_ref": line.external_ref,
        "status": line.status,
        "matched_journal_line_id": line.matched_journal_line_id,
        "clearing_group_id": getattr(line, "clearing_group_id", None),
        "created_at": line.created_at,
    }


def serialize_statement(stmt: m.BankStatement, lines: list[m.BankStatementLine] | None = None) -> dict:
    rows = lines or []
    unmatched = sum(1 for ln in rows if ln.status == "unmatched")
    matched = sum(1 for ln in rows if ln.status == "matched")
    ignored = sum(1 for ln in rows if ln.status == "ignored")
    return {
        "id": stmt.id,
        "account_id": stmt.account_id,
        "statement_date": stmt.statement_date,
        "opening_balance": float(stmt.opening_balance or 0),
        "closing_balance": float(stmt.closing_balance or 0),
        "status": stmt.status,
        "notes": stmt.notes,
        "reconciled_at": stmt.reconciled_at,
        "created_by": stmt.created_by,
        "created_at": stmt.created_at,
        "line_count": len(rows),
        "unmatched_count": unmatched,
        "matched_count": matched,
        "ignored_count": ignored,
        "lines": [serialize_line(ln) for ln in rows],
    }


def journal_line_signed_amount(line: m.JournalEntryLine) -> float:
    """Asset convention: debit positive (inflow), credit negative (outflow)."""
    return round(float(line.debit or 0) - float(line.credit or 0), 2)


async def get_liquid_account(db: AsyncSession, tenant_id: str, account_id: str) -> m.Account:
    from app.accounting import assert_account_active

    account = (
        await db.execute(
            select(m.Account).where(m.Account.id == account_id, m.Account.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not (account.is_cash_account or account.is_bank_account):
        raise HTTPException(
            status_code=400,
            detail="Account must be marked as cash or bank for reconciliation",
        )
    assert_account_active(account)
    return account


async def list_liquid_accounts(db: AsyncSession, tenant_id: str) -> list[m.Account]:
    return list(
        (
            await db.execute(
                select(m.Account)
                .where(
                    m.Account.tenant_id == tenant_id,
                    or_(m.Account.is_cash_account.is_(True), m.Account.is_bank_account.is_(True)),
                    m.Account.is_active.is_(True),
                )
                .order_by(m.Account.code)
            )
        )
        .scalars()
        .all()
    )


async def get_statement(db: AsyncSession, tenant_id: str, statement_id: str) -> m.BankStatement:
    row = (
        await db.execute(
            select(m.BankStatement).where(
                m.BankStatement.id == statement_id,
                m.BankStatement.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    return row


async def list_statement_lines(
    db: AsyncSession, tenant_id: str, statement_id: str
) -> list[m.BankStatementLine]:
    return list(
        (
            await db.execute(
                select(m.BankStatementLine)
                .where(
                    m.BankStatementLine.tenant_id == tenant_id,
                    m.BankStatementLine.statement_id == statement_id,
                )
                .order_by(m.BankStatementLine.txn_date.asc(), m.BankStatementLine.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


async def list_statements(db: AsyncSession, tenant_id: str) -> list[m.BankStatement]:
    return list(
        (
            await db.execute(
                select(m.BankStatement)
                .where(m.BankStatement.tenant_id == tenant_id)
                .order_by(m.BankStatement.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


def _parse_dt(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if len(text) == 10:
        return datetime.strptime(text, "%Y-%m-%d")
    return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)


async def create_statement(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    account_id: str,
    statement_date: str | datetime | None,
    opening_balance: float,
    closing_balance: float,
    notes: str | None = None,
    lines: list[dict] | None = None,
) -> m.BankStatement:
    await get_liquid_account(db, tenant_id, account_id)
    stmt = m.BankStatement(
        tenant_id=tenant_id,
        account_id=account_id,
        statement_date=_parse_dt(statement_date),
        opening_balance=float(opening_balance or 0),
        closing_balance=float(closing_balance or 0),
        status="in_progress" if lines else "draft",
        notes=notes,
        created_by=user_id,
    )
    db.add(stmt)
    await db.flush()
    for raw in lines or []:
        amount = float(raw.get("amount") or 0)
        if abs(amount) < 1e-9:
            raise HTTPException(status_code=400, detail="Statement line amount cannot be zero")
        db.add(
            m.BankStatementLine(
                tenant_id=tenant_id,
                statement_id=stmt.id,
                txn_date=_parse_dt(raw.get("txn_date") or statement_date),
                amount=amount,
                description=(raw.get("description") or "").strip() or None,
                external_ref=(raw.get("external_ref") or "").strip() or None,
                status="unmatched",
            )
        )
    await db.flush()
    return stmt


async def import_statement_from_feed(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    account_id: str,
    content: str,
    filename: str | None = None,
    opening_balance: float | None = None,
    closing_balance: float | None = None,
    statement_date: str | datetime | None = None,
    notes: str | None = None,
) -> tuple[m.BankStatement, dict]:
    """Parse CSV/OFX content and create a bank statement."""
    from app.bank_feed import parse_bank_feed

    parsed = parse_bank_feed(content, filename=filename)
    lines = parsed["lines"]
    net = round(sum(float(ln["amount"]) for ln in lines), 2)

    open_bal = (
        float(opening_balance)
        if opening_balance is not None
        else (
            float(parsed["opening_balance"])
            if parsed.get("opening_balance") is not None
            else 0.0
        )
    )
    if closing_balance is not None:
        close_bal = float(closing_balance)
    elif parsed.get("closing_balance") is not None:
        close_bal = float(parsed["closing_balance"])
    else:
        close_bal = round(open_bal + net, 2)

    # Statement date: explicit, else latest txn date
    if statement_date is None:
        statement_date = max(ln["txn_date"] for ln in lines)

    note_bits = [notes] if notes else []
    note_bits.append(f"Imported {parsed['format'].upper()} ({len(lines)} lines)")
    if filename:
        note_bits.append(filename)

    stmt = await create_statement(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        account_id=account_id,
        statement_date=statement_date,
        opening_balance=open_bal,
        closing_balance=close_bal,
        notes=" · ".join(note_bits),
        lines=lines,
    )
    meta = {
        "format": parsed["format"],
        "filename": filename,
        "line_count": len(lines),
        "net_amount": net,
        "opening_balance": open_bal,
        "closing_balance": close_bal,
    }
    return stmt, meta


async def unmatched_book_lines(
    db: AsyncSession,
    *,
    tenant_id: str,
    account_id: str,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> list[dict]:
    """Journal lines on the liquid account not already matched on any statement."""
    matched_ids = {
        mid
        for mid in (
            await db.execute(
                select(m.BankStatementLine.matched_journal_line_id).where(
                    m.BankStatementLine.tenant_id == tenant_id,
                    m.BankStatementLine.matched_journal_line_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
        if mid
    }
    grouped_ids = {
        mid
        for mid in (
            await db.execute(
                select(m.BankClearingBookLink.journal_line_id).where(
                    m.BankClearingBookLink.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .all()
        if mid
    }
    matched_ids |= grouped_ids

    q = (
        select(m.JournalEntryLine, m.JournalEntry)
        .join(m.JournalEntry, m.JournalEntry.id == m.JournalEntryLine.journal_entry_id)
        .where(
            m.JournalEntryLine.tenant_id == tenant_id,
            m.JournalEntryLine.account_id == account_id,
        )
        .order_by(m.JournalEntry.entry_date.asc())
    )
    if from_date:
        q = q.where(m.JournalEntry.entry_date >= from_date)
    if to_date:
        q = q.where(m.JournalEntry.entry_date <= to_date)

    out: list[dict] = []
    for line, entry in (await db.execute(q)).all():
        if line.id in matched_ids:
            continue
        signed = journal_line_signed_amount(line)
        if abs(signed) < 1e-9:
            continue
        out.append(
            {
                "journal_line_id": line.id,
                "journal_entry_id": entry.id,
                "entry_number": entry.entry_number,
                "entry_date": entry.entry_date,
                "description": line.description or entry.description,
                "reference": entry.reference,
                "source_type": entry.source_type,
                "debit": float(line.debit or 0),
                "credit": float(line.credit or 0),
                "signed_amount": signed,
            }
        )
    return out


async def match_line(
    db: AsyncSession,
    *,
    tenant_id: str,
    line_id: str,
    journal_line_id: str,
) -> m.BankStatementLine:
    # Schema BankStatementMatchBody rejects blank journal_line_id → 422; keep defense.
    jid = (journal_line_id or "").strip()
    if not jid:
        raise HTTPException(status_code=422, detail="journal_line_id is required")
    line = (
        await db.execute(
            select(m.BankStatementLine).where(
                m.BankStatementLine.id == line_id,
                m.BankStatementLine.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Statement line not found")
    if line.status == "matched":
        raise HTTPException(status_code=409, detail="Line already matched")
    if getattr(line, "clearing_group_id", None):
        raise HTTPException(status_code=409, detail="Line is in a clearing group; dissolve it first")

    stmt = await get_statement(db, tenant_id, line.statement_id)
    if stmt.status == "reconciled":
        raise HTTPException(status_code=409, detail="Statement is already reconciled")

    jl = (
        await db.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.id == jid,
                m.JournalEntryLine.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not jl:
        raise HTTPException(status_code=404, detail="Journal line not found")
    if jl.account_id != stmt.account_id:
        raise HTTPException(status_code=400, detail="Journal line is not on this bank/cash account")

    already = (
        await db.execute(
            select(m.BankStatementLine.id).where(
                m.BankStatementLine.tenant_id == tenant_id,
                m.BankStatementLine.matched_journal_line_id == jid,
            )
        )
    ).scalar_one_or_none()
    if already:
        raise HTTPException(status_code=409, detail="Journal line already matched to another statement line")
    grouped = (
        await db.execute(
            select(m.BankClearingBookLink.id).where(
                m.BankClearingBookLink.tenant_id == tenant_id,
                m.BankClearingBookLink.journal_line_id == jid,
            )
        )
    ).scalar_one_or_none()
    if grouped:
        raise HTTPException(status_code=409, detail="Journal line already in a clearing group")

    signed = journal_line_signed_amount(jl)
    bank_amt = round(float(line.amount), 2)
    if abs(signed - bank_amt) > 0.01:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AMOUNT_MISMATCH",
                "message": "Bank line amount does not match journal line signed amount",
                "bank_amount": bank_amt,
                "journal_signed_amount": signed,
            },
        )

    line.matched_journal_line_id = jl.id
    line.status = "matched"
    line.clearing_group_id = None
    if stmt.status == "draft":
        stmt.status = "in_progress"
    await db.flush()
    return line


async def unmatch_line(db: AsyncSession, *, tenant_id: str, line_id: str) -> m.BankStatementLine:
    line = (
        await db.execute(
            select(m.BankStatementLine).where(
                m.BankStatementLine.id == line_id,
                m.BankStatementLine.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Statement line not found")
    stmt = await get_statement(db, tenant_id, line.statement_id)
    if stmt.status == "reconciled":
        raise HTTPException(status_code=409, detail="Statement is already reconciled")
    if getattr(line, "clearing_group_id", None):
        await dissolve_clearing_group(db, tenant_id=tenant_id, group_id=line.clearing_group_id)
        await db.refresh(line)
        return line
    line.matched_journal_line_id = None
    line.status = "unmatched"
    await db.flush()
    return line


async def ignore_line(db: AsyncSession, *, tenant_id: str, line_id: str) -> m.BankStatementLine:
    line = (
        await db.execute(
            select(m.BankStatementLine).where(
                m.BankStatementLine.id == line_id,
                m.BankStatementLine.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Statement line not found")
    stmt = await get_statement(db, tenant_id, line.statement_id)
    if stmt.status == "reconciled":
        raise HTTPException(status_code=409, detail="Statement is already reconciled")
    if line.status == "matched" or getattr(line, "clearing_group_id", None):
        raise HTTPException(status_code=409, detail="Unmatch the line or clearing group before ignoring")
    line.matched_journal_line_id = None
    line.clearing_group_id = None
    line.status = "ignored"
    await db.flush()
    return line


async def complete_statement(db: AsyncSession, *, tenant_id: str, statement_id: str) -> m.BankStatement:
    stmt = await get_statement(db, tenant_id, statement_id)
    if stmt.status == "reconciled":
        return stmt
    lines = await list_statement_lines(db, tenant_id, statement_id)
    if not lines:
        raise HTTPException(status_code=400, detail="Cannot reconcile an empty statement")
    open_lines = [ln for ln in lines if ln.status == "unmatched"]
    if open_lines:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "UNMATCHED_LINES",
                "message": f"{len(open_lines)} statement line(s) still unmatched",
                "unmatched_count": len(open_lines),
            },
        )

    net = sum(float(ln.amount) for ln in lines)
    expected_closing = round(float(stmt.opening_balance or 0) + net, 2)
    if abs(expected_closing - float(stmt.closing_balance or 0)) > 0.01:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STATEMENT_ARITHMETIC",
                "message": "opening + matched/unignored lines does not equal closing balance",
                "expected_closing": expected_closing,
                "statement_closing": float(stmt.closing_balance or 0),
            },
        )

    stmt.status = "reconciled"
    stmt.reconciled_at = datetime.utcnow()
    await db.flush()
    return stmt


async def auto_match_suggestions(
    db: AsyncSession,
    *,
    tenant_id: str,
    statement_id: str,
    date_window_days: int = 7,
) -> list[dict]:
    """Suggest bank↔book matches with confidence (does not persist).

    Confidence:
      high   — exact amount + (reference hit or same calendar day)
      medium — exact amount within date window
      low    — exact amount + overlapping description tokens (wider date ok)
    """
    stmt = await get_statement(db, tenant_id, statement_id)
    lines = await list_statement_lines(db, tenant_id, statement_id)
    book = await unmatched_book_lines(db, tenant_id=tenant_id, account_id=stmt.account_id)
    used: set[str] = set()
    suggestions: list[dict] = []

    def _tokens(text: str | None) -> set[str]:
        if not text:
            return set()
        return {t for t in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if len(t) >= 3}

    def _ref_hit(bank_line: m.BankStatementLine, jl: dict) -> bool:
        refs = {
            (bank_line.external_ref or "").strip().lower(),
            (bank_line.description or "").strip().lower(),
        }
        refs.discard("")
        candidates = {
            str(jl.get("entry_number") or "").strip().lower(),
            str(jl.get("description") or "").strip().lower(),
            str(jl.get("source_type") or "").strip().lower(),
        }
        # Pull journal entry reference when present on book row
        if jl.get("reference"):
            candidates.add(str(jl["reference"]).strip().lower())
        candidates.discard("")
        for r in refs:
            for c in candidates:
                if r and c and (r == c or r in c or c in r):
                    return True
        return False

    for bl in lines:
        if bl.status != "unmatched":
            continue
        amt = round(float(bl.amount), 2)
        bank_tokens = _tokens(bl.description) | _tokens(bl.external_ref)
        best = None
        for jl in book:
            if jl["journal_line_id"] in used:
                continue
            if abs(jl["signed_amount"] - amt) > 0.01:
                continue
            delta = (
                abs((bl.txn_date.date() - jl["entry_date"].date()).days)
                if bl.txn_date and jl.get("entry_date")
                else 999
            )
            ref_hit = _ref_hit(bl, jl)
            book_tokens = _tokens(jl.get("description"))
            overlap = len(bank_tokens & book_tokens) if bank_tokens and book_tokens else 0

            if ref_hit or delta == 0:
                confidence = "high"
                score = 100 - min(delta, 10)
                if ref_hit:
                    score += 20
            elif delta <= date_window_days:
                confidence = "medium"
                score = 70 - delta
            elif overlap >= 1 and delta <= max(date_window_days * 2, 14):
                confidence = "low"
                score = 40 + overlap * 5 - min(delta, 20)
            else:
                continue

            candidate = {
                "statement_line_id": bl.id,
                "journal_line_id": jl["journal_line_id"],
                "bank_amount": amt,
                "journal_signed_amount": jl["signed_amount"],
                "date_delta_days": delta,
                "entry_number": jl["entry_number"],
                "confidence": confidence,
                "score": score,
                "ref_match": ref_hit,
                "description_overlap": overlap,
                "bank_description": bl.description,
                "book_description": jl.get("description"),
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
        if best:
            used.add(best["journal_line_id"])
            suggestions.append(best)

    suggestions.sort(key=lambda s: (-s["score"], s["date_delta_days"]))
    return suggestions


async def apply_auto_matches(
    db: AsyncSession,
    *,
    tenant_id: str,
    statement_id: str,
    min_confidence: str = "high",
    date_window_days: int = 7,
) -> dict:
    """Persist suggestions at or above min_confidence (high > medium > low)."""
    order = {"high": 3, "medium": 2, "low": 1}
    # Defense in depth: BankAutoClearBody.min_confidence Literal rejects blank/unknown with 422.
    # Empty/garbage used to coerce to high via `or "high"` / order.get(..., 3).
    key = (min_confidence or "").strip().lower()
    if key not in order:
        raise HTTPException(
            status_code=400,
            detail="min_confidence must be high, medium, or low",
        )
    floor = order[key]
    suggestions = await auto_match_suggestions(
        db,
        tenant_id=tenant_id,
        statement_id=statement_id,
        date_window_days=date_window_days,
    )
    applied: list[dict] = []
    skipped: list[dict] = []
    for sug in suggestions:
        level = order.get(sug.get("confidence") or "", 0)
        if level < floor:
            skipped.append({**sug, "reason": "below_min_confidence"})
            continue
        try:
            line = await match_line(
                db,
                tenant_id=tenant_id,
                line_id=sug["statement_line_id"],
                journal_line_id=sug["journal_line_id"],
            )
            applied.append(
                {
                    "statement_line_id": line.id,
                    "journal_line_id": sug["journal_line_id"],
                    "confidence": sug["confidence"],
                    "entry_number": sug.get("entry_number"),
                }
            )
        except HTTPException as exc:
            skipped.append({**sug, "reason": str(exc.detail)})
    return {
        "statement_id": statement_id,
        "min_confidence": min_confidence,
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "applied": applied,
        "skipped": skipped,
    }


def serialize_clearing_group(
    group: m.BankClearingGroup,
    *,
    bank_line_ids: list[str],
    journal_line_ids: list[str],
    bank_total: float,
    book_total: float,
) -> dict:
    return {
        "id": group.id,
        "statement_id": group.statement_id,
        "notes": group.notes,
        "created_by": group.created_by,
        "created_at": group.created_at,
        "statement_line_ids": bank_line_ids,
        "journal_line_ids": journal_line_ids,
        "bank_total": bank_total,
        "book_total": book_total,
    }


async def list_clearing_groups(
    db: AsyncSession, *, tenant_id: str, statement_id: str
) -> list[dict]:
    groups = list(
        (
            await db.execute(
                select(m.BankClearingGroup).where(
                    m.BankClearingGroup.tenant_id == tenant_id,
                    m.BankClearingGroup.statement_id == statement_id,
                )
            )
        )
        .scalars()
        .all()
    )
    out: list[dict] = []
    for g in groups:
        bank_lines = list(
            (
                await db.execute(
                    select(m.BankStatementLine).where(
                        m.BankStatementLine.tenant_id == tenant_id,
                        m.BankStatementLine.clearing_group_id == g.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        links = list(
            (
                await db.execute(
                    select(m.BankClearingBookLink).where(
                        m.BankClearingBookLink.tenant_id == tenant_id,
                        m.BankClearingBookLink.group_id == g.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        bank_total = round(sum(float(ln.amount) for ln in bank_lines), 2)
        book_total = 0.0
        jl_ids = [lk.journal_line_id for lk in links]
        if jl_ids:
            jlines = list(
                (
                    await db.execute(
                        select(m.JournalEntryLine).where(m.JournalEntryLine.id.in_(jl_ids))
                    )
                )
                .scalars()
                .all()
            )
            book_total = round(sum(journal_line_signed_amount(jl) for jl in jlines), 2)
        out.append(
            serialize_clearing_group(
                g,
                bank_line_ids=[ln.id for ln in bank_lines],
                journal_line_ids=jl_ids,
                bank_total=bank_total,
                book_total=book_total,
            )
        )
    return out


async def create_clearing_group(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    statement_id: str,
    statement_line_ids: list[str],
    journal_line_ids: list[str],
    notes: str | None = None,
) -> dict:
    """Match N bank lines to M book lines when signed totals are equal."""
    stmt = await get_statement(db, tenant_id, statement_id)
    if stmt.status == "reconciled":
        raise HTTPException(status_code=409, detail="Statement is already reconciled")

    bank_ids = list(dict.fromkeys([str(x) for x in (statement_line_ids or []) if x]))
    book_ids = list(dict.fromkeys([str(x) for x in (journal_line_ids or []) if x]))
    # Schema BankClearGroupBody rejects empty id lists → 422; keep defense-in-depth.
    if not bank_ids or not book_ids:
        raise HTTPException(
            status_code=422,
            detail="clearing group requires at least one statement line and one journal line",
        )
    if len(bank_ids) == 1 and len(book_ids) == 1:
        line = await match_line(
            db, tenant_id=tenant_id, line_id=bank_ids[0], journal_line_id=book_ids[0]
        )
        return {
            "mode": "single",
            "line": serialize_line(line),
            "statement_line_ids": bank_ids,
            "journal_line_ids": book_ids,
        }

    bank_lines: list[m.BankStatementLine] = []
    for lid in bank_ids:
        row = (
            await db.execute(
                select(m.BankStatementLine).where(
                    m.BankStatementLine.id == lid,
                    m.BankStatementLine.tenant_id == tenant_id,
                    m.BankStatementLine.statement_id == statement_id,
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail=f"Statement line not found: {lid}")
        if row.status != "unmatched":
            raise HTTPException(status_code=409, detail=f"Statement line {lid} is not unmatched")
        bank_lines.append(row)

    book_lines: list[m.JournalEntryLine] = []
    for jid in book_ids:
        jl = (
            await db.execute(
                select(m.JournalEntryLine).where(
                    m.JournalEntryLine.id == jid,
                    m.JournalEntryLine.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not jl:
            raise HTTPException(status_code=404, detail=f"Journal line not found: {jid}")
        if jl.account_id != stmt.account_id:
            raise HTTPException(status_code=400, detail="Journal line is not on this bank/cash account")
        already = (
            await db.execute(
                select(m.BankStatementLine.id).where(
                    m.BankStatementLine.tenant_id == tenant_id,
                    m.BankStatementLine.matched_journal_line_id == jid,
                )
            )
        ).scalar_one_or_none()
        if already:
            raise HTTPException(status_code=409, detail=f"Journal line {jid} already matched")
        grouped = (
            await db.execute(
                select(m.BankClearingBookLink.id).where(
                    m.BankClearingBookLink.tenant_id == tenant_id,
                    m.BankClearingBookLink.journal_line_id == jid,
                )
            )
        ).scalar_one_or_none()
        if grouped:
            raise HTTPException(status_code=409, detail=f"Journal line {jid} already in a clearing group")
        book_lines.append(jl)

    bank_total = round(sum(float(ln.amount) for ln in bank_lines), 2)
    book_total = round(sum(journal_line_signed_amount(jl) for jl in book_lines), 2)
    if abs(bank_total - book_total) > 0.01:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "AMOUNT_MISMATCH",
                "message": "Sum of bank lines must equal sum of journal signed amounts",
                "bank_total": bank_total,
                "book_total": book_total,
            },
        )

    group = m.BankClearingGroup(
        tenant_id=tenant_id,
        statement_id=statement_id,
        notes=notes,
        created_by=user_id,
    )
    db.add(group)
    await db.flush()

    for ln in bank_lines:
        ln.status = "matched"
        ln.clearing_group_id = group.id
        ln.matched_journal_line_id = None
    for jl in book_lines:
        db.add(
            m.BankClearingBookLink(
                tenant_id=tenant_id,
                group_id=group.id,
                journal_line_id=jl.id,
            )
        )
    if stmt.status == "draft":
        stmt.status = "in_progress"
    await db.flush()

    return {
        "mode": "group",
        "group": serialize_clearing_group(
            group,
            bank_line_ids=bank_ids,
            journal_line_ids=book_ids,
            bank_total=bank_total,
            book_total=book_total,
        ),
    }


async def dissolve_clearing_group(
    db: AsyncSession, *, tenant_id: str, group_id: str
) -> dict:
    group = (
        await db.execute(
            select(m.BankClearingGroup).where(
                m.BankClearingGroup.id == group_id,
                m.BankClearingGroup.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Clearing group not found")
    stmt = await get_statement(db, tenant_id, group.statement_id)
    if stmt.status == "reconciled":
        raise HTTPException(status_code=409, detail="Statement is already reconciled")

    bank_lines = list(
        (
            await db.execute(
                select(m.BankStatementLine).where(
                    m.BankStatementLine.tenant_id == tenant_id,
                    m.BankStatementLine.clearing_group_id == group.id,
                )
            )
        )
        .scalars()
        .all()
    )
    for ln in bank_lines:
        ln.clearing_group_id = None
        ln.matched_journal_line_id = None
        ln.status = "unmatched"

    links = list(
        (
            await db.execute(
                select(m.BankClearingBookLink).where(
                    m.BankClearingBookLink.tenant_id == tenant_id,
                    m.BankClearingBookLink.group_id == group.id,
                )
            )
        )
        .scalars()
        .all()
    )
    for lk in links:
        await db.delete(lk)
    await db.delete(group)
    await db.flush()
    return {
        "id": group_id,
        "dissolved": True,
        "statement_line_ids": [ln.id for ln in bank_lines],
    }
