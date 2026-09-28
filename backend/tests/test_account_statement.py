"""Account statement from posted journals."""

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
async def test_account_statement_follows_coa_opening(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200
    opening = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=headers,
        json={
            "reference": "STMT-OPEN",
            "lines": [
                {"account_code": "1000", "amount": 200},
                {"account_code": "2000", "amount": 50},
            ],
        },
    )
    assert opening.status_code == 200, opening.text
    accounts = (await ac.get("/api/v1/accounting/accounts", headers=headers)).json()["data"]
    cash = next(a for a in accounts if a["code"] == "1000")
    stmt = await ac.get(
        f"/api/v1/accounting/accounts/{cash['id']}/statement",
        headers=headers,
    )
    assert stmt.status_code == 200, stmt.text
    data = stmt.json()["data"]
    assert data["code"] == "1000"
    assert abs(float(data["closing_balance"]) - 200) < 0.01
    assert data["lines"]
