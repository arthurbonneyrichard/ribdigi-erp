"""Balance sheet as_of + comparative periods (BR-14.5)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest
from sqlalchemy import select

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_balance_sheet_as_of_and_compare(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    # Seed COA + opening balances
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200
    opening = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=headers,
        json={
            "reference": "BS-OPEN",
            "lines": [
                {"account_code": "1000", "amount": 1000},
                {"account_code": "2000", "amount": 200},
            ],
        },
    )
    assert opening.status_code == 200, opening.text

    live = await ac.get("/api/v1/reports/balance-sheet", headers=headers)
    assert live.status_code == 200, live.text
    live_data = live.json()["data"]
    assert live_data["mode"] == "balances"
    assert live_data["balanced"] is True
    assert abs(float(live_data["total_assets"]) - 1000) < 0.01

    # Post an operating expense journal "today"
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        description="Later expense",
        source_type="manual",
        lines=[
            {"account_code": "6000", "debit": 50, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 50},
        ],
    )
    await db_session.commit()

    # Backdate that journal into the future relative to as_of cutoff
    future = datetime.utcnow() + timedelta(days=5)
    je = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.description == "Later expense",
            )
        )
    ).scalar_one()
    je.entry_date = future
    await db_session.commit()

    as_of = datetime.utcnow().strftime("%Y-%m-%d")
    cut = await ac.get(
        f"/api/v1/reports/balance-sheet?as_of={as_of}",
        headers=headers,
    )
    assert cut.status_code == 200, cut.text
    cut_data = cut.json()["data"]
    assert cut_data["mode"] == "journals"
    assert cut_data["as_of"] == as_of
    # Future expense excluded → cash still 1000
    assert abs(float(cut_data["total_assets"]) - 1000) < 0.01
    assert cut_data["balanced"] is True

    # Live balances include the future-dated JE (balance updates on post regardless of entry_date)
    live2 = await ac.get("/api/v1/reports/balance-sheet", headers=headers)
    assert abs(float(live2.json()["data"]["total_assets"]) - 950) < 0.01

    # Comparative: prior month-end should still see opening (posted "now")
    # Move opening JE into prior month so prior_period has assets
    open_je = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.source_type == "coa_opening",
            )
        )
    ).scalar_one()
    open_je.entry_date = datetime.utcnow().replace(day=1) - timedelta(days=10)
    await db_session.commit()

    compared = await ac.get(
        f"/api/v1/accounting/balance-sheet?as_of={as_of}&compare=prior_period",
        headers=headers,
    )
    assert compared.status_code == 200, compared.text
    cdata = compared.json()["data"]
    assert cdata["compare"]
    assert cdata["compare"]["mode"] == "prior_period"
    assert "deltas" in cdata["compare"]
    cash = next(r for r in cdata["assets"] if r["code"] == "1000")
    assert "prior_balance" in cash
    assert "delta" in cash
    # Prior month-end includes opening (1000 cash); current as_of excludes future expense → same
    assert abs(float(cash["balance"]) - 1000) < 0.01
    assert abs(float(cash["prior_balance"]) - 1000) < 0.01
