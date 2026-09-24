"""Opening stock entry (BR-5.2)."""

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
async def test_opening_stock_posts_qty_and_journal(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    units = await ac.get("/api/v1/catalog/units", headers=headers)
    pcs_id = next(u["id"] for u in units.json()["data"] if u["code"] == "PCS")
    prod = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Open Widget",
            "sku": "OPEN-1",
            "cost_price": 5,
            "selling_price": 8,
            "stock_qty": 0,
            "unit_id": pcs_id,
        },
    )
    assert prod.status_code == 200, prod.text
    pid = prod.json()["data"]["id"]

    whs = await ac.get("/api/v1/warehouses", headers=headers)
    assert whs.status_code == 200, whs.text
    warehouse_id = (whs.json()["data"] or [None])[0]
    warehouse_id = warehouse_id["id"] if warehouse_id else None

    r = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={
            "reference": "FY2026-OPEN",
            "notes": "Go-live stock",
            "post_journal": True,
            "lines": [
                {
                    "product_id": pid,
                    "quantity": 20,
                    "warehouse_id": warehouse_id,
                    "unit_cost": 5,
                }
            ],
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["reference"] == "FY2026-OPEN"
    assert data["inventory_value"] == 100.0
    assert data["journal_id"]
    assert data["lines"][0]["quantity_base"] == 20.0
    assert data["lines"][0]["stock_qty"] == 20.0

    product = await ac.get(f"/api/v1/products/{pid}", headers=headers)
    assert float(product.json()["data"]["stock_qty"]) == 20.0

    hist = await ac.get("/api/v1/inventory/opening-stock", headers=headers)
    assert hist.status_code == 200, hist.text
    assert any(float(m["quantity"]) == 20.0 for m in hist.json()["data"])

    # Journal balanced Dr 1200 / Cr 3000
    je = (
        await db_session.execute(
            select(m.JournalEntry).where(m.JournalEntry.id == data["journal_id"])
        )
    ).scalar_one()
    assert je.source_type == "opening_stock"
    lines = (
        await db_session.execute(
            select(m.JournalEntryLine).where(m.JournalEntryLine.journal_entry_id == je.id)
        )
    ).scalars().all()
    by_code = {}
    for line in lines:
        acct = await db_session.get(m.Account, line.account_id)
        by_code[acct.code] = (float(line.debit), float(line.credit))
    assert by_code["1200"] == (100.0, 0.0)
    assert by_code["3000"] == (0.0, 100.0)


@pytest.mark.asyncio
async def test_opening_stock_case_uom_and_skip_journal(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    units = await ac.get("/api/v1/catalog/units", headers=headers)
    by_code = {u["code"]: u for u in units.json()["data"]}
    pcs_id = by_code["PCS"]["id"]
    box = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={
            "code": "CASE6",
            "name": "Case of 6",
            "base_unit_id": pcs_id,
            "conversion_ratio": 6,
        },
    )
    assert box.status_code == 200, box.text
    box_id = box.json()["data"]["id"]

    prod = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Case Open",
            "sku": "OPEN-CASE",
            "cost_price": 2,
            "selling_price": 3,
            "stock_qty": 0,
            "unit_id": pcs_id,
        },
    )
    pid = prod.json()["data"]["id"]

    r = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={
            "post_journal": False,
            "lines": [{"product_id": pid, "quantity": 2, "unit_id": box_id}],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["journal_id"] is None
    assert r.json()["data"]["lines"][0]["quantity_base"] == 12.0
    product = await ac.get(f"/api/v1/products/{pid}", headers=headers)
    assert float(product.json()["data"]["stock_qty"]) == 12.0


@pytest.mark.asyncio
async def test_opening_stock_requires_inventory_write(client):
    ac, seed = client
    # cashier lacks inventory:write
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={"lines": [{"product_id": seed["p1"].id, "quantity": 1}]},
    )
    assert r.status_code == 403
