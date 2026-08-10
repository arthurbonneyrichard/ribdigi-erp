"""Stage 14 A1: journal store dimension + store-filtered P&L / cash-flow / journal list."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from app.stores import create_store
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_expense_and_manual_journal_store_filters_pnl_cashflow(client, db_session):
    ac, seed = client
    mgr = await _mgr(ac)
    super_h = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    store_a = await create_store(
        db_session, tenant_id=tenant_id, code="A1SA", name="A1 Store A"
    )
    store_b = await create_store(
        db_session, tenant_id=tenant_id, code="A1SB", name="A1 Store B"
    )
    foreign = await create_store(
        db_session, tenant_id=seed["t2"].id, code="A1FX", name="Foreign Store"
    )
    await db_session.commit()

    amount_a = 40.0
    amount_b = 25.0

    exp_a = await ac.post(
        "/api/v1/expenses",
        headers=mgr,
        json={
            "category": "General",
            "amount": amount_a,
            "description": "Store A expense",
            "payment_method": "cash",
            "store_id": store_a.id,
        },
    )
    assert exp_a.status_code == 200, exp_a.text
    assert exp_a.json()["data"]["status"] == "approved"
    exp_a_id = exp_a.json()["data"]["id"]

    exp_b = await ac.post(
        "/api/v1/expenses",
        headers=mgr,
        json={
            "category": "General",
            "amount": amount_b,
            "description": "Store B expense",
            "payment_method": "cash",
            "store_id": store_b.id,
        },
    )
    assert exp_b.status_code == 200, exp_b.text
    exp_b_id = exp_b.json()["data"]["id"]

    je_a = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == exp_a_id,
            )
        )
    ).scalar_one()
    assert je_a.store_id == store_a.id

    je_b = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == exp_b_id,
            )
        )
    ).scalar_one()
    assert je_b.store_id == store_b.id

    # Manual journal with store + foreign store rejected
    denied = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=super_h,
        json={
            "description": "Foreign store journal",
            "store_id": foreign.id,
            "lines": [
                {"account_code": "6000", "debit": 10, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 10},
            ],
        },
    )
    assert denied.status_code == 404, denied.text

    manual = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=super_h,
        json={
            "description": "Manual store A adjust",
            "store_id": store_a.id,
            "lines": [
                {"account_code": "6000", "debit": 5, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 5},
            ],
        },
    )
    assert manual.status_code == 200, manual.text
    mdata = manual.json()["data"]
    assert mdata["store_id"] == store_a.id

    listed_a = await ac.get(
        "/api/v1/accounting/journal-entries",
        headers=super_h,
        params={"store_id": store_a.id},
    )
    assert listed_a.status_code == 200, listed_a.text
    listed_ids = {r["id"] for r in listed_a.json()["data"]}
    assert je_a.id in listed_ids
    assert mdata["id"] in listed_ids
    assert je_b.id not in listed_ids

    today = datetime.utcnow().strftime("%Y-%m-%d")
    pnl_a = await ac.get(
        "/api/v1/accounting/profit-loss",
        headers=super_h,
        params={"from_date": today, "to_date": today, "store_id": store_a.id},
    )
    assert pnl_a.status_code == 200, pnl_a.text
    pdata_a = pnl_a.json()["data"]
    assert pdata_a["store_id"] == store_a.id
    # expense 40 + manual 5
    assert float(pdata_a["operating_expenses"]) == pytest.approx(amount_a + 5)

    pnl_b = await ac.get(
        "/api/v1/reports/profit-loss",
        headers=super_h,
        params={"from_date": today, "to_date": today, "store_id": store_b.id},
    )
    assert pnl_b.status_code == 200, pnl_b.text
    pdata_b = pnl_b.json()["data"]
    assert pdata_b["store_id"] == store_b.id
    assert float(pdata_b["operating_expenses"]) == pytest.approx(amount_b)

    cf_a = await ac.get(
        "/api/v1/reports/cash-flow",
        headers=super_h,
        params={"from_date": today, "to_date": today, "store_id": store_a.id},
    )
    assert cf_a.status_code == 200, cf_a.text
    cdata = cf_a.json()["data"]
    assert cdata["store_id"] == store_a.id
    assert float(cdata.get("outflows") or 0) >= amount_a + 5

    bad_pnl = await ac.get(
        "/api/v1/accounting/profit-loss",
        headers=super_h,
        params={"store_id": foreign.id},
    )
    assert bad_pnl.status_code == 404, bad_pnl.text
