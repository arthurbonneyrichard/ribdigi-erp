"""Expense reference year-series numbering (BR-9.2 / BR-20.4)."""

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
async def test_expense_auto_reference_numbering(client, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)
    year = datetime.utcnow().year

    settings = await ac.patch(
        "/api/v1/expenses/settings",
        headers=admin,
        json={"expense_numbering": {"prefix": "EXP", "next_number": 15}},
    )
    assert settings.status_code == 200, settings.text
    assert settings.json()["data"]["expense_numbering"]["preview"] == f"EXP-{year}-0015"
    assert "levels" in settings.json()["data"]

    cats = await ac.get("/api/v1/expenses/categories", headers=admin)
    assert cats.status_code == 200, cats.text
    cat_id = cats.json()["data"][0]["id"]

    created = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={
            "category_id": cat_id,
            "amount": 12.5,
            "description": "Numbering smoke",
            "payment_method": "cash",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["reference"] == f"EXP-{year}-0015"

    explicit = await ac.post(
        "/api/v1/expenses",
        headers=admin,
        json={
            "category_id": cat_id,
            "amount": 8,
            "description": "Vendor invoice",
            "payment_method": "cash",
            "reference": "VENDOR-99",
        },
    )
    assert explicit.status_code == 200, explicit.text
    assert explicit.json()["data"]["reference"] == "VENDOR-99"

    nxt = await ac.get("/api/v1/expenses/settings", headers=admin)
    assert nxt.status_code == 200
    # Only auto-allocated expense advanced the series.
    assert nxt.json()["data"]["expense_numbering"]["preview"] == f"EXP-{year}-0016"
