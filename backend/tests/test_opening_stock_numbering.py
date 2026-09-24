"""Opening stock reference year-series numbering (BR-5.2 / BR-20.4)."""

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
async def test_opening_stock_auto_reference_numbering(client, seeded):
    ac, seed = client
    admin = await _admin(ac, seed)
    year = datetime.utcnow().year

    settings = await ac.patch(
        "/api/v1/inventory/settings",
        headers=admin,
        json={"opening_stock_numbering": {"prefix": "OS", "next_number": 55}},
    )
    assert settings.status_code == 200, settings.text
    data = settings.json()["data"]
    assert data["opening_stock_numbering"]["preview"] == f"OS-{year}-0055"
    assert "stock_transfer_numbering" in data
    assert "stock_count_numbering" in data

    units = await ac.get("/api/v1/catalog/units", headers=admin)
    pcs_id = next(u["id"] for u in units.json()["data"] if u["code"] == "PCS")
    prod = await ac.post(
        "/api/v1/products",
        headers=admin,
        json={
            "name": "OS Number Widget",
            "sku": "OS-NUM-1",
            "cost_price": 4,
            "selling_price": 7,
            "stock_qty": 0,
            "unit_id": pcs_id,
        },
    )
    assert prod.status_code == 200, prod.text
    pid = prod.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=admin,
        json={
            "post_journal": True,
            "lines": [{"product_id": pid, "quantity": 3, "unit_cost": 4}],
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    assert body["reference"] == f"OS-{year}-0055"
    assert body["journal_id"]

    explicit = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=admin,
        json={
            "reference": "FY26-MANUAL",
            "post_journal": True,
            "lines": [{"product_id": pid, "quantity": 1, "unit_cost": 4}],
        },
    )
    assert explicit.status_code == 200, explicit.text
    assert explicit.json()["data"]["reference"] == "FY26-MANUAL"

    nxt = await ac.get("/api/v1/inventory/settings", headers=admin)
    assert nxt.status_code == 200
    assert nxt.json()["data"]["opening_stock_numbering"]["preview"] == f"OS-{year}-0056"
