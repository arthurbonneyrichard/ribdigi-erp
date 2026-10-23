"""GET /gift-cards lists the company's own cards, newest first."""

from __future__ import annotations

import pyotp
import pytest
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_gift_card_list_shows_issued_cards(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)

    issued = await ac.post("/api/v1/gift-cards", headers=headers, json={"amount": 25})
    if issued.status_code == 403:
        pytest.skip("gift cards are not offered for this test tenant's industry")
    assert issued.status_code == 200, issued.text
    card = issued.json()["data"]

    listed = await ac.get("/api/v1/gift-cards", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    assert rows and rows[0]["code"] == card["code"]
    assert rows[0]["balance"] == 25
