"""Other income posts a real journal to 4400."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_other_income_posts_ledger(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    await ac.get("/api/v1/accounting/accounts", headers=headers)
    created = await ac.post(
        "/api/v1/incomes",
        headers=headers,
        json={"description": "Hall rental", "amount": 40, "payment_method": "cash"},
    )
    assert created.status_code == 200, created.text
    row = created.json()["data"]
    assert float(row["amount"]) == 40
    assert row["journal_entry_id"]
    listed = await ac.get("/api/v1/incomes", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(i["id"] == row["id"] for i in listed.json()["data"])
    accounts = (await ac.get("/api/v1/accounting/accounts", headers=headers)).json()["data"]
    income = next(a for a in accounts if a["code"] == "4400")
    stmt = await ac.get(
        f"/api/v1/accounting/accounts/{income['id']}/statement",
        headers=headers,
    )
    assert stmt.status_code == 200, stmt.text
    assert abs(float(stmt.json()["data"]["closing_balance"]) - 40) < 0.01
