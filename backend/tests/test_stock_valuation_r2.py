"""Stage 9 R2: stock valuation report — qty × cost_price (BR-14.2 / BR-5.4)."""

from __future__ import annotations

import pytest

from app import models as m
from app.stores import create_store, warehouse_for_store
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_stock_valuation_math_and_warehouse_filter(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    store_a = await create_store(db_session, tenant_id=tenant_id, code="R2A", name="R2 Store A")
    store_b = await create_store(db_session, tenant_id=tenant_id, code="R2B", name="R2 Store B")
    wh_a = await warehouse_for_store(db_session, tenant_id, store_a.id)
    wh_b = await warehouse_for_store(db_session, tenant_id, store_b.id)

    p1 = seed["p1"]
    p1.cost_price = 2.5
    p1.stock_qty = 0
    p2 = m.Product(
        tenant_id=tenant_id,
        name="R2 Widget B",
        sku="R2-B",
        cost_price=4,
        selling_price=9,
        stock_qty=0,
        is_active=True,
    )
    db_session.add(p2)
    await db_session.flush()

    db_session.add_all(
        [
            m.WarehouseStock(
                tenant_id=tenant_id,
                warehouse_id=wh_a.id,
                product_id=p1.id,
                quantity=10,
            ),
            m.WarehouseStock(
                tenant_id=tenant_id,
                warehouse_id=wh_b.id,
                product_id=p1.id,
                quantity=4,
            ),
            m.WarehouseStock(
                tenant_id=tenant_id,
                warehouse_id=wh_a.id,
                product_id=p2.id,
                quantity=3,
            ),
        ]
    )
    await db_session.commit()

    all_val = await ac.get("/api/v1/reports/inventory/valuation", headers=headers)
    assert all_val.status_code == 200, all_val.text
    body = all_val.json()["data"]
    assert body["costing_method"] == "standard_cost"
    assert "FIFO" in body["costing_method_note"]
    assert "not used" in body["costing_method_note"].lower()
    # 10*2.5 + 4*2.5 + 3*4 = 25 + 10 + 12 = 47
    assert body["total_value"] == pytest.approx(47.0)
    assert body["total_quantity"] == pytest.approx(17.0)
    assert body["line_count"] == 3
    assert len(body["by_warehouse"]) == 2

    by_wh = {w["warehouse_id"]: w for w in body["by_warehouse"]}
    assert by_wh[wh_a.id]["total_value"] == pytest.approx(37.0)  # 25 + 12
    assert by_wh[wh_b.id]["total_value"] == pytest.approx(10.0)

    filtered = await ac.get(
        "/api/v1/reports/inventory/valuation",
        headers=headers,
        params={"warehouse_id": wh_b.id},
    )
    assert filtered.status_code == 200, filtered.text
    fbody = filtered.json()["data"]
    assert fbody["total_value"] == pytest.approx(10.0)
    assert fbody["line_count"] == 1
    assert fbody["items"][0]["cost_price"] == pytest.approx(2.5)
    assert fbody["items"][0]["value"] == pytest.approx(10.0)

    by_store = await ac.get(
        "/api/v1/reports/inventory/valuation",
        headers=headers,
        params={"store_id": store_a.id},
    )
    assert by_store.status_code == 200, by_store.text
    sbody = by_store.json()["data"]
    assert sbody["warehouse_id"] == wh_a.id
    assert sbody["total_value"] == pytest.approx(37.0)


@pytest.mark.asyncio
async def test_stock_valuation_product_fallback_and_isolation(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    product = seed["p1"]
    product.cost_price = 3
    product.stock_qty = 5
    product.is_active = True
    await db_session.commit()

    # No warehouse stock rows → fallback to product.stock_qty
    val = await ac.get("/api/v1/reports/inventory/valuation", headers=headers)
    assert val.status_code == 200, val.text
    body = val.json()["data"]
    row = next(i for i in body["items"] if i["product_id"] == product.id)
    assert row["quantity"] == pytest.approx(5.0)
    assert row["value"] == pytest.approx(15.0)

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    cross = await ac.get("/api/v1/reports/inventory/valuation", headers=beta)
    assert cross.status_code in (200, 403)
    if cross.status_code == 200:
        ids = {i["product_id"] for i in cross.json()["data"]["items"]}
        assert product.id not in ids


@pytest.mark.asyncio
async def test_stock_valuation_export_type():
    from app.report_export import EXPORTABLE, flatten_report

    assert "inventory_valuation" in EXPORTABLE
    rows, lines, title = flatten_report(
        "inventory_valuation",
        {
            "costing_method": "standard_cost",
            "total_value": 20,
            "items": [
                {
                    "sku": "A-1",
                    "quantity": 4,
                    "cost_price": 5,
                    "value": 20,
                }
            ],
        },
    )
    assert title == "Stock Valuation"
    assert rows[0]["sku"] == "A-1"
    assert any("standard_cost" in line for line in lines)
