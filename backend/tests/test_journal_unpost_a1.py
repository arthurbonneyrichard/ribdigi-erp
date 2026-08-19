"""Stage 3 A1: journal unpost within open fiscal period (BR-10.2)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import bank_recon as recon
from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_unpost_reverses_balances_and_status(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    exp = await accounting_svc.get_account_by_code(db_session, tenant_id, "6000")
    cash_before = float(cash.balance or 0)
    exp_before = float(exp.balance or 0)

    posted = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "A1 adjusting",
            "lines": [
                {"account_code": "6000", "debit": 40, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 40},
            ],
        },
    )
    assert posted.status_code == 200, posted.text
    entry = posted.json()["data"]
    assert entry["status"] == "posted"

    await db_session.refresh(cash)
    await db_session.refresh(exp)
    assert float(cash.balance or 0) == cash_before - 40
    assert float(exp.balance or 0) == exp_before + 40

    got = await ac.get(f"/api/v1/accounting/journal-entries/{entry['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["entry_number"] == entry["entry_number"]

    unposted = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry['id']}/unpost",
        headers=headers,
    )
    assert unposted.status_code == 200, unposted.text
    body = unposted.json()["data"]
    assert body["status"] == "unposted"

    await db_session.refresh(cash)
    await db_session.refresh(exp)
    assert float(cash.balance or 0) == cash_before
    assert float(exp.balance or 0) == exp_before

    again = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry['id']}/unpost",
        headers=headers,
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "JOURNAL_NOT_POSTED"


@pytest.mark.asyncio
async def test_unpost_blocked_outside_open_fiscal_period(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    seed["t1"].fiscal_year_start = "01-01"
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    entry = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        description="Prior year JE",
        lines=[
            {"account_code": "6000", "debit": 15, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 15},
        ],
    )
    entry.entry_date = datetime(datetime.utcnow().year - 1, 6, 15)
    await db_session.commit()

    r = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry.id}/unpost",
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "FISCAL_PERIOD_CLOSED"


@pytest.mark.asyncio
async def test_unpost_blocked_when_bank_matched(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")

    entry = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        description="Deposit for recon",
        lines=[
            {"account_code": "1000", "debit": 55, "credit": 0},
            {"account_code": "4000", "debit": 0, "credit": 55},
        ],
    )
    await db_session.flush()
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
        user_id=seed["admin1"].id,
        account_id=cash.id,
        statement_date=datetime.utcnow(),
        opening_balance=0,
        closing_balance=55,
        lines=[{"txn_date": datetime.utcnow(), "amount": 55, "description": "Deposit"}],
    )
    lines = await recon.list_statement_lines(db_session, tenant_id, stmt.id)
    await recon.match_line(
        db_session,
        tenant_id=tenant_id,
        line_id=lines[0].id,
        journal_line_id=cash_line.id,
    )
    await db_session.commit()

    r = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry.id}/unpost",
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "JOURNAL_RECONCILED"


@pytest.mark.asyncio
async def test_unpost_tenant_isolation(client, db_session):
    ac, seed = client
    tenant_a = seed["t1"].id
    tenant_b = seed["t2"].id
    beta_admin = m.User(
        tenant_id=tenant_b,
        email="acct@beta.example.com",
        full_name="Beta Accountant",
        password_hash=hash_password("SecurePass123!"),
        role="accountant",
        email_verified=True,
        permissions=permissions_for_role("accountant"),
        totp_enabled=False,
    )
    db_session.add(beta_admin)
    await accounting_svc.ensure_default_accounts(db_session, tenant_a)
    entry = await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_a,
        user_id=seed["admin1"].id,
        description="Alpha only",
        lines=[
            {"account_code": "6000", "debit": 10, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 10},
        ],
    )
    await db_session.commit()

    headers_b = await auth_headers(ac, email="acct@beta.example.com", tenant_slug="beta")
    r = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry.id}/unpost",
        headers=headers_b,
    )
    assert r.status_code == 404

    g = await ac.get(
        f"/api/v1/accounting/journal-entries/{entry.id}",
        headers=headers_b,
    )
    assert g.status_code == 404


@pytest.mark.asyncio
async def test_fiscal_year_bounds_helpers():
    start, end = accounting_svc.fiscal_year_bounds("04-01", as_of=datetime(2026, 3, 15).date())
    assert start.isoformat() == "2025-04-01"
    assert end.isoformat() == "2026-04-01"
    assert accounting_svc.entry_in_open_fiscal_period(
        datetime(2025, 5, 1), "04-01", as_of=datetime(2026, 3, 15)
    )
    assert not accounting_svc.entry_in_open_fiscal_period(
        datetime(2024, 5, 1), "04-01", as_of=datetime(2026, 3, 15)
    )
