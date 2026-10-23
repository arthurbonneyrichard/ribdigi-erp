"""One open till shift per cashier; the current-shift lookup never 500s on duplicates."""

from __future__ import annotations

import pyotp
import pytest
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _close_current(ac, headers):
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    assert cur.status_code == 200, cur.text
    data = cur.json().get("data")
    if data:
        sid = data.get("session_id") or data.get("id")
        await ac.post(f"/api/v1/pos/sessions/{sid}/close", headers=headers, json={"actual_cash": 0})


@pytest.mark.asyncio
async def test_second_open_keeps_one_open_shift(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    await _close_current(ac, headers)

    first = await ac.post("/api/v1/pos/sessions/open", headers=headers, json={"opening_cash": 0})
    assert first.status_code == 200, first.text
    opened = first.json()["data"]["session_id"]

    # A second start-up request (till page and page frame together) must not open another.
    second = await ac.post("/api/v1/pos/sessions/open", headers=headers, json={"opening_cash": 0})
    assert second.status_code in (200, 409), second.text
    if second.status_code == 200:
        assert second.json()["data"]["session_id"] == opened

    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    assert cur.status_code == 200, cur.text
    assert cur.json()["data"]["session_id"] == opened
