"""Cash/bank transfer reference year-series numbering (BR-10.3 / BR-20.4)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_cash_transfer_auto_reference_numbering(client, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)
    year = datetime.utcnow().year

    settings = await ac.patch(
        "/api/v1/accounting/settings",
        headers=admin,
        json={"cash_transfer_numbering": {"prefix": "XFER", "next_number": 42}},
    )
    assert settings.status_code == 200, settings.text
    data = settings.json()["data"]
    assert data["cash_transfer_numbering"]["preview"] == f"XFER-{year}-0042"
    assert "journal_numbering" in data

    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=admin)
    assert liq.status_code == 200, liq.text
    by_code = {a["code"]: a for a in liq.json()["data"]}
    cash = by_code["1000"]

    created = await ac.post(
        "/api/v1/accounting/transfers",
        headers=admin,
        json={"kind": "deposit", "to_account_id": cash["id"], "amount": 25},
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["reference"] == f"XFER-{year}-0042"

    explicit = await ac.post(
        "/api/v1/accounting/transfers",
        headers=admin,
        json={
            "kind": "deposit",
            "to_account_id": cash["id"],
            "amount": 10,
            "reference": "BANK-SLIP-9",
        },
    )
    assert explicit.status_code == 200, explicit.text
    assert explicit.json()["data"]["reference"] == "BANK-SLIP-9"

    nxt = await ac.get("/api/v1/accounting/settings", headers=admin)
    assert nxt.status_code == 200
    # Only auto-allocated transfer advanced the series.
    assert nxt.json()["data"]["cash_transfer_numbering"]["preview"] == f"XFER-{year}-0043"
