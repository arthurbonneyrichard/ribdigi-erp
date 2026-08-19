"""Stage 14 E1: expense category → COA posting + approve → journal → TB/P&L/cash-flow."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_category_account_maps_expense_journal_and_statements(client, db_session):
    ac, seed = client
    mgr = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    # Custom expense COA under Operating Expenses family
    created_acct = await ac.post(
        "/api/v1/accounting/accounts",
        headers=super_h,
        json={
            "code": "6100",
            "name": "Travel Expense",
            "account_type": "expense",
        },
    )
    assert created_acct.status_code == 200, created_acct.text
    travel_acct_id = created_acct.json()["data"]["id"]

    # Reject non-expense account link
    cash = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    bad = await ac.post(
        "/api/v1/expenses/categories",
        headers=mgr,
        json={
            "code": "BADGL",
            "name": "Bad GL",
            "budget_amount": 0,
            "account_id": cash.id,
        },
    )
    assert bad.status_code == 400, bad.text
    assert bad.json()["detail"]["code"] == "INVALID_EXPENSE_ACCOUNT"

    cat = await ac.post(
        "/api/v1/expenses/categories",
        headers=mgr,
        json={
            "code": "TRAVELGL",
            "name": "Travel (GL mapped)",
            "budget_amount": 500,
            "account_id": travel_acct_id,
        },
    )
    assert cat.status_code == 200, cat.text
    cdata = cat.json()["data"]
    assert cdata["account_id"] == travel_acct_id
    assert cdata["account_code"] == "6100"
    category_id = cdata["id"]

    amount = 75.0
    created = await ac.post(
        "/api/v1/expenses",
        headers=mgr,
        json={
            "category_id": category_id,
            "amount": amount,
            "description": "Airport taxi",
            "payment_method": "cash",
            "payee": "City Cab",
        },
    )
    assert created.status_code == 200, created.text
    expense = created.json()["data"]
    assert expense["status"] == "approved"
    expense_id = expense["id"]

    je = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == expense_id,
            )
        )
    ).scalar_one()
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == je.id)
        )
    ).scalars().all()
    by_acct = {
        ln.account_id: (float(ln.debit or 0), float(ln.credit or 0)) for ln in lines
    }
    assert by_acct[travel_acct_id][0] == pytest.approx(amount)
    cash_acct = await accounting_svc.get_account_by_code(db_session, tenant_id, "1000")
    assert by_acct[cash_acct.id][1] == pytest.approx(amount)

    # Fallback 6000 when category has no account_id
    bare = await ac.post(
        "/api/v1/expenses/categories",
        headers=mgr,
        json={"code": "MISCGL", "name": "Misc unmapped", "budget_amount": 0},
    )
    assert bare.status_code == 200, bare.text
    bare_id = bare.json()["data"]["id"]
    assert bare.json()["data"]["account_id"] is None

    exp2 = await ac.post(
        "/api/v1/expenses",
        headers=mgr,
        json={
            "category_id": bare_id,
            "amount": 20,
            "description": "Office snacks",
            "payment_method": "cash",
        },
    )
    assert exp2.status_code == 200, exp2.text
    exp2_id = exp2.json()["data"]["id"]
    je2 = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == exp2_id,
            )
        )
    ).scalar_one()
    lines2 = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == je2.id)
        )
    ).scalars().all()
    opx = await accounting_svc.get_account_by_code(db_session, tenant_id, "6000")
    assert any(
        ln.account_id == opx.id and float(ln.debit or 0) == pytest.approx(20)
        for ln in lines2
    )

    await db_session.commit()
    tb = await ac.get("/api/v1/accounting/trial-balance", headers=super_h)
    assert tb.status_code == 200, tb.text
    tb_rows = {r["code"]: r for r in tb.json()["data"]["rows"]}
    assert float(tb_rows["6100"]["balance"]) == pytest.approx(amount)
    assert float(tb_rows["6100"]["debit"]) == pytest.approx(amount)

    today = datetime.utcnow().strftime("%Y-%m-%d")
    pnl = await ac.get(
        "/api/v1/accounting/profit-loss",
        headers=super_h,
        params={"from_date": today, "to_date": today},
    )
    assert pnl.status_code == 200, pnl.text
    pdata = pnl.json()["data"]
    # Travel 75 (6100) + Misc 20 (6000) → operating expenses
    assert float(pdata["operating_expenses"]) == pytest.approx(amount + 20)
    codes = {a["code"] for a in pdata["accounts"]}
    assert "6100" in codes and "6000" in codes

    cf = await ac.get(
        "/api/v1/reports/cash-flow",
        headers=super_h,
        params={"from_date": today, "to_date": today},
    )
    assert cf.status_code == 200, cf.text
    cdata = cf.json()["data"]
    operating = cdata.get("operating") or {}
    # Cash-basis expense posts Cr cash → operating outflow
    assert float(operating.get("net") or 0) <= -amount
    assert float(cdata.get("outflows") or 0) >= amount


@pytest.mark.asyncio
async def test_patch_category_account_and_clear(client, db_session):
    ac, seed = client
    mgr = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    acct = await ac.post(
        "/api/v1/accounting/accounts",
        headers=super_h,
        json={"code": "6200", "name": "Utilities GL", "account_type": "expense"},
    )
    assert acct.status_code == 200, acct.text
    acct_id = acct.json()["data"]["id"]

    cat = await ac.post(
        "/api/v1/expenses/categories",
        headers=mgr,
        json={"code": "UTILMAP", "name": "Utilities mapped", "budget_amount": 0},
    )
    assert cat.status_code == 200, cat.text
    cat_id = cat.json()["data"]["id"]

    linked = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=mgr,
        json={"account_id": acct_id},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["data"]["account_id"] == acct_id
    assert linked.json()["data"]["account_code"] == "6200"

    cleared = await ac.patch(
        f"/api/v1/expenses/categories/{cat_id}",
        headers=mgr,
        json={"clear_account": True},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["account_id"] is None
