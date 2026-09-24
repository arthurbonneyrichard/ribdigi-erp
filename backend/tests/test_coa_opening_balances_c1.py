"""COA opening balances (BR-10.1)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_coa_opening_posts_balanced_journal_with_equity_plug(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    # Ensure COA seeded
    accounts = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert accounts.status_code == 200, accounts.text

    status0 = await ac.get("/api/v1/accounting/opening-balances", headers=headers)
    assert status0.status_code == 200
    assert status0.json()["data"]["posted"] is False

    r = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=headers,
        json={
            "reference": "FY2026-COA",
            "notes": "Go-live openings",
            "lines": [
                {"account_code": "1000", "amount": 500},
                {"account_code": "1010", "amount": 1500},
                {"account_code": "2000", "amount": 300},
            ],
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["reference"] == "FY2026-COA"
    assert data["total_debit"] == data["total_credit"]
    # Assets 2000 - liability 300 = 1700 equity plug credit
    assert abs(float(data["equity_plug_amount"]) - 1700.0) < 0.01
    assert data["journal_id"]

    cash = next(a for a in (await ac.get("/api/v1/accounting/accounts", headers=headers)).json()["data"] if a["code"] == "1000")
    assert float(cash["opening_balance"]) == 500.0
    assert float(cash["balance"]) == 500.0

    equity = next(a for a in (await ac.get("/api/v1/accounting/accounts", headers=headers)).json()["data"] if a["code"] == "3000")
    assert float(equity["balance"]) == 1700.0

    status1 = await ac.get("/api/v1/accounting/opening-balances", headers=headers)
    assert status1.json()["data"]["posted"] is True

    dup = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=headers,
        json={"lines": [{"account_code": "1000", "amount": 1}]},
    )
    assert dup.status_code == 409

    je = (
        await db_session.execute(
            select(m.JournalEntry).where(m.JournalEntry.id == data["journal_id"])
        )
    ).scalar_one()
    assert je.source_type == "coa_opening"


@pytest.mark.asyncio
async def test_patch_account_name(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    accounts = await ac.get("/api/v1/accounting/accounts", headers=headers)
    cash = next(a for a in accounts.json()["data"] if a["code"] == "1000")
    r = await ac.patch(
        f"/api/v1/accounting/accounts/{cash['id']}",
        headers=headers,
        json={"name": "Main Till Cash"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["name"] == "Main Till Cash"


@pytest.mark.asyncio
async def test_coa_opening_requires_accounting_write(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=headers,
        json={"lines": [{"account_code": "1000", "amount": 10}]},
    )
    assert r.status_code == 403
