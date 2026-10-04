"""Trial balance as_of (BR-10.6 / BR-14.5)."""

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
async def test_trial_balance_as_of_excludes_future_journals(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200
    opening = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=headers,
        json={
            "reference": "TB-OPEN",
            "lines": [
                {"account_code": "1000", "amount": 500},
                {"account_code": "2000", "amount": 100},
            ],
        },
    )
    assert opening.status_code == 200, opening.text

    live = await ac.get("/api/v1/reports/trial-balance", headers=headers)
    assert live.status_code == 200, live.text
    live_data = live.json()["data"]
    assert live_data["mode"] == "balances"
    assert live_data["balanced"] is True
    cash = next(r for r in live_data["rows"] if r["code"] == "1000")
    assert abs(float(cash["debit"]) - 500) < 0.01

    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["u1"].id,
        description="Future TB expense",
        source_type="manual",
        lines=[
            {"account_code": "6000", "debit": 40, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 40},
        ],
    )
    await db_session.commit()

    je = (
        await db_session.execute(
            select(m.JournalEntry).where(
                m.JournalEntry.tenant_id == tenant_id,
                m.JournalEntry.description == "Future TB expense",
            )
        )
    ).scalar_one()
    je.entry_date = datetime.utcnow() + timedelta(days=7)
    await db_session.commit()

    as_of = datetime.utcnow().strftime("%Y-%m-%d")
    cut = await ac.get(
        f"/api/v1/accounting/trial-balance?as_of={as_of}",
        headers=headers,
    )
    assert cut.status_code == 200, cut.text
    cut_data = cut.json()["data"]
    assert cut_data["mode"] == "journals"
    assert cut_data["as_of"] == as_of
    assert cut_data["balanced"] is True
    cash_cut = next(r for r in cut_data["rows"] if r["code"] == "1000")
    assert abs(float(cash_cut["debit"]) - 500) < 0.01
    assert not any(r["code"] == "6000" for r in cut_data["rows"])

    live2 = await ac.get("/api/v1/reports/trial-balance", headers=headers)
    cash_live = next(r for r in live2.json()["data"]["rows"] if r["code"] == "1000")
    assert abs(float(cash_live["debit"]) - 460) < 0.01
