"""Sign-in tells the app the company's business type so each role lands on its own home screen."""

from __future__ import annotations

import pytest

from tests.conftest import set_tenant_industry

pytestmark = pytest.mark.asyncio


async def test_login_returns_company_industry(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    res = await ac.post(
        "/api/v1/auth/login",
        json={"tenant_id": "alpha", "email": "cashier@alpha.example.com", "password": "SecurePass123!"},
    )
    assert res.status_code == 200, res.text
    user = res.json()["data"]["user"]
    assert user["role"] == "cashier"
    assert user["industry"] == "restaurant"
