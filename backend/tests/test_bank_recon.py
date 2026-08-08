"""Bank reconciliation service tests."""

from datetime import datetime

import pytest

from app import accounting as accounting_svc
from app import bank_recon as recon
from app import models as m


@pytest.mark.asyncio
async def test_bank_statement_match_and_complete(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    assert cash.is_cash_account is True

    # Deposit: Dr Cash 100 / Cr Sales 100
    entry = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        description="Customer deposit",
        lines=[
            {"account_code": "1000", "debit": 100, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 100},
        ],
        source_type="manual",
    )
    await db_session.flush()

    from sqlalchemy import select

    cash_line = (
        await db_session.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.journal_entry_id == entry.id,
                m.JournalEntryLine.account_id == cash.id,
            )
        )
    ).scalar_one()

    stmt = await recon.create_statement(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        account_id=cash.id,
        statement_date=datetime.utcnow(),
        opening_balance=0,
        closing_balance=100,
        lines=[{"txn_date": datetime.utcnow(), "amount": 100, "description": "Deposit"}],
    )
    lines = await recon.list_statement_lines(db_session, tenant_id, stmt.id)
    assert len(lines) == 1

    matched = await recon.match_line(
        db_session,
        tenant_id=tenant_id,
        line_id=lines[0].id,
        journal_line_id=cash_line.id,
    )
    assert matched.status == "matched"

    done = await recon.complete_statement(db_session, tenant_id=tenant_id, statement_id=stmt.id)
    await db_session.commit()
    assert done.status == "reconciled"
    assert done.reconciled_at is not None


@pytest.mark.asyncio
async def test_match_rejects_amount_mismatch(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")

    entry = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        description="Small deposit",
        lines=[
            {"account_code": "1000", "debit": 50, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 50},
        ],
    )
    from sqlalchemy import select
    from fastapi import HTTPException

    cash_line = (
        await db_session.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.journal_entry_id == entry.id,
                m.JournalEntryLine.account_id == cash.id,
            )
        )
    ).scalar_one()

    stmt = await recon.create_statement(
        db_session,
        tenant_id=tenant_id,
        user_id=None,
        account_id=cash.id,
        statement_date="2026-08-08",
        opening_balance=0,
        closing_balance=100,
        lines=[{"amount": 100, "description": "Wrong"}],
    )
    line = (await recon.list_statement_lines(db_session, tenant_id, stmt.id))[0]
    with pytest.raises(HTTPException) as exc:
        await recon.match_line(
            db_session,
            tenant_id=tenant_id,
            line_id=line.id,
            journal_line_id=cash_line.id,
        )
    assert exc.value.status_code == 400


def test_ensure_defaults_include_bank():
    assert any(row[0] == "1010" for row in accounting_svc.DEFAULT_ACCOUNTS)


@pytest.mark.asyncio
async def test_auto_clear_applies_high_confidence_matches(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")

    entry = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        description="Wire deposit REF-AUTO-9",
        reference="REF-AUTO-9",
        lines=[
            {"account_code": "1000", "debit": 250, "credit": 0, "description": "Wire deposit REF-AUTO-9"},
            {"account_code": "4000", "debit": 0, "credit": 250},
        ],
    )
    from sqlalchemy import select

    cash_line = (
        await db_session.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.journal_entry_id == entry.id,
                m.JournalEntryLine.account_id == cash.id,
            )
        )
    ).scalar_one()

    day = datetime.utcnow()
    stmt = await recon.create_statement(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        account_id=cash.id,
        statement_date=day,
        opening_balance=0,
        closing_balance=250,
        lines=[
            {
                "txn_date": day,
                "amount": 250,
                "description": "Incoming wire",
                "external_ref": "REF-AUTO-9",
            }
        ],
    )

    suggestions = await recon.auto_match_suggestions(
        db_session, tenant_id=tenant_id, statement_id=stmt.id
    )
    assert len(suggestions) == 1
    assert suggestions[0]["confidence"] == "high"
    assert suggestions[0]["journal_line_id"] == cash_line.id
    assert suggestions[0]["ref_match"] is True

    result = await recon.apply_auto_matches(
        db_session,
        tenant_id=tenant_id,
        statement_id=stmt.id,
        min_confidence="high",
    )
    await db_session.commit()
    assert result["applied_count"] == 1
    lines = await recon.list_statement_lines(db_session, tenant_id, stmt.id)
    assert lines[0].status == "matched"
    assert lines[0].matched_journal_line_id == cash_line.id


@pytest.mark.asyncio
async def test_many_to_one_clearing_group(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")

    # Two deposits totaling 150
    e1 = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        description="Deposit A",
        lines=[
            {"account_code": "1000", "debit": 100, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 100},
        ],
    )
    e2 = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        description="Deposit B",
        lines=[
            {"account_code": "1000", "debit": 50, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 50},
        ],
    )
    from sqlalchemy import select

    jl1 = (
        await db_session.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.journal_entry_id == e1.id,
                m.JournalEntryLine.account_id == cash.id,
            )
        )
    ).scalar_one()
    jl2 = (
        await db_session.execute(
            select(m.JournalEntryLine).where(
                m.JournalEntryLine.journal_entry_id == e2.id,
                m.JournalEntryLine.account_id == cash.id,
            )
        )
    ).scalar_one()

    day = datetime.utcnow()
    stmt = await recon.create_statement(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        account_id=cash.id,
        statement_date=day,
        opening_balance=0,
        closing_balance=150,
        lines=[
            {"txn_date": day, "amount": 90, "description": "Part 1"},
            {"txn_date": day, "amount": 60, "description": "Part 2"},
        ],
    )
    bank_lines = await recon.list_statement_lines(db_session, tenant_id, stmt.id)
    result = await recon.create_clearing_group(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        statement_id=stmt.id,
        statement_line_ids=[bank_lines[0].id, bank_lines[1].id],
        journal_line_ids=[jl1.id, jl2.id],
    )
    await db_session.commit()
    assert result["mode"] == "group"
    assert result["group"]["bank_total"] == 150.0
    assert result["group"]["book_total"] == 150.0

    bank_lines = await recon.list_statement_lines(db_session, tenant_id, stmt.id)
    assert all(ln.status == "matched" for ln in bank_lines)
    assert all(ln.clearing_group_id == result["group"]["id"] for ln in bank_lines)

    unmatched = await recon.unmatched_book_lines(
        db_session, tenant_id=tenant_id, account_id=cash.id
    )
    assert jl1.id not in {u["journal_line_id"] for u in unmatched}
    assert jl2.id not in {u["journal_line_id"] for u in unmatched}

    done = await recon.complete_statement(db_session, tenant_id=tenant_id, statement_id=stmt.id)
    assert done.status == "reconciled"
