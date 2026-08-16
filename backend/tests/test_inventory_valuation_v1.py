"""Standard-cost stock valuation report (BR-14.2 / BR-5.4)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.inventory import get_or_create_warehouse_stock
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_standard_valuation_and_warehouse_filter(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.cost_price = 5
    product.stock_qty = 10
    await db_session.commit()

    company = await ac.get(
        "/api/v1/reports/inventory/valuation?method=standard",
        headers=headers,
    )
    assert company.status_code == 200, company.text
    data = company.json()["data"]
    assert data["method"] == "standard"
    assert abs(float(data["total_value"]) - 50) < 0.01
    row = next(i for i in data["items"] if i["product_id"] == product.id)
    assert abs(float(row["unit_cost"]) - 5) < 0.01
    assert abs(float(row["quantity"]) - 10) < 0.01
    assert abs(float(row["value"]) - 50) < 0.01

    wh = m.Warehouse(tenant_id=tenant_id, name="Val WH", code="VAL-WH")
    db_session.add(wh)
    await db_session.flush()
    stock = await get_or_create_warehouse_stock(
        db_session, tenant_id=tenant_id, warehouse_id=wh.id, product_id=product.id
    )
    stock.quantity = 4
    await db_session.commit()

    by_wh = await ac.get(
        f"/api/v1/reports/inventory/valuation?method=standard&warehouse_id={wh.id}",
        headers=headers,
    )
    assert by_wh.status_code == 200, by_wh.text
    wdata = by_wh.json()["data"]
    assert wdata["warehouse_id"] == wh.id
    assert abs(float(wdata["total_quantity"]) - 4) < 0.01
    assert abs(float(wdata["total_value"]) - 20) < 0.01

    for method in ("fifo", "lifo", "weighted_average", "average", "", "  "):
        bad = await ac.get(
            f"/api/v1/reports/inventory/valuation?method={method}",
            headers=headers,
        )
        assert bad.status_code == 422, bad.text

    missing = await ac.get(
        "/api/v1/reports/inventory/valuation?warehouse_id=does-not-exist",
        headers=headers,
    )
    assert missing.status_code == 404
