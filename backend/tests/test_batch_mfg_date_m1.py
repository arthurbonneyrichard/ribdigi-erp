"""Batch manufacturing_date on stock-in and list (BR-5.1)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stock_in_persists_manufacturing_and_expiry(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    product_id = seed["p1"].id
    mfg = datetime.utcnow() - timedelta(days=30)
    exp = datetime.utcnow() + timedelta(days=180)

    received = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 12,
            "batch_number": "LOT-MFG-1",
            "manufacturing_date": mfg.isoformat(),
            "expiry_date": exp.isoformat(),
        },
    )
    assert received.status_code == 200, received.text
    batch = received.json()["data"].get("batch") or {}
    assert batch.get("batch_number") == "LOT-MFG-1"
    assert batch.get("manufacturing_date")
    assert str(batch["manufacturing_date"])[:10] == mfg.date().isoformat()
    assert batch.get("expiry_date")
    assert str(batch["expiry_date"])[:10] == exp.date().isoformat()

    listed = await ac.get(f"/api/v1/products/{product_id}/batches", headers=headers)
    assert listed.status_code == 200
    row = next(b for b in listed.json()["data"] if b["batch_number"] == "LOT-MFG-1")
    assert str(row["manufacturing_date"])[:10] == mfg.date().isoformat()
    assert str(row["expiry_date"])[:10] == exp.date().isoformat()
