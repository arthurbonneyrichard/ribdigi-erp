"""Stage 9 R2: stock valuation report — qty × cost_price (BR-14.2 / BR-5.4)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.stores import create_store, warehouse_for_store
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stock_valuation_math_and_warehouse_filter(client, db_session):
    ac, seed = client
    # Cost figures are redacted for store_manager; use admin for valuation math.
    headers = await _super(ac, seed)
    mgr_headers = await _mgr(ac)
    tenant_id = seed["t1"].id
    cid = seed["c1"].id
    mgr = seed["mgr1"]

    store_a = await create_store(
        db_session,
        tenant_id=tenant_id,
        company_id=cid,
        code="R2A",
        name="R2 Store A",
        manager_id=mgr.id,
    )
    store_b = await create_store(
        db_session,
        tenant_id=tenant_id,
        company_id=cid,
        code="R2B",
        name="R2 Store B",
        manager_id=None,
    )
    wh_a = await warehouse_for_store(db_session, tenant_id, store_a.id, company_id=cid)
    wh_b = await warehouse_for_store(db_session, tenant_id, store_b.id, company_id=cid)

    p1 = seed["p1"]
    p1.cost_price = 2.5
    p1.stock_qty = 0
    p2 = m.Product(
        tenant_id=tenant_id,
        company_id=cid,
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
                company_id=cid,
                warehouse_id=wh_a.id,
                product_id=p1.id,
                quantity=10,
            ),
            m.WarehouseStock(
                tenant_id=tenant_id,
                company_id=cid,
                warehouse_id=wh_b.id,
                product_id=p1.id,
                quantity=4,
            ),
            m.WarehouseStock(
                tenant_id=tenant_id,
                company_id=cid,
                warehouse_id=wh_a.id,
                product_id=p2.id,
                quantity=3,
            ),
        ]
    )
    await db_session.commit()

    # store_manager: only managed store A; cost fields redacted.
    scoped = await ac.get("/api/v1/reports/inventory/valuation", headers=mgr_headers)
    assert scoped.status_code == 200, scoped.text
    body = scoped.json()["data"]
    assert body["costing_method"] == "standard_cost"
    assert "FIFO" in body["costing_method_note"]
    assert "not used" in body["costing_method_note"].lower()
    assert body["total_quantity"] == pytest.approx(13.0)
    assert body["line_count"] == 2
    assert len(body["by_warehouse"]) == 1
    assert body["by_warehouse"][0]["warehouse_id"] == wh_a.id
    # Cost redaction for store_manager
    assert body["total_value"] is None
    assert body["by_warehouse"][0]["total_value"] is None

    # Admin/super: full cost math for managed warehouse A (10*2.5 + 3*4 = 37)
    filtered = await ac.get(
        "/api/v1/reports/inventory/valuation",
        headers=headers,
        params={"warehouse_id": wh_a.id},
    )
    assert filtered.status_code == 200, filtered.text
    fbody = filtered.json()["data"]
    assert fbody["total_value"] == pytest.approx(37.0)

    denied = await ac.get(
        "/api/v1/reports/inventory/valuation",
        headers=mgr_headers,
        params={"warehouse_id": wh_b.id},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "STORE_SCOPE_DENIED"

    by_store = await ac.get(
        "/api/v1/reports/inventory/valuation",
        headers=headers,
        params={"store_id": store_a.id},
    )
    assert by_store.status_code == 200, by_store.text
    sbody = by_store.json()["data"]
    assert sbody["warehouse_id"] == wh_a.id
    assert sbody["total_value"] == pytest.approx(37.0)

    # store_manager cannot select an unmanaged store
    cross_store = await ac.get(
        "/api/v1/reports/inventory/valuation",
        headers=mgr_headers,
        params={"store_id": store_b.id},
    )
    assert cross_store.status_code == 403


@pytest.mark.asyncio
async def test_stock_valuation_product_fallback_and_isolation(client, db_session):
    """Product.stock_qty fallback is for tenant-wide roles; managers omit it."""
    ac, seed = client
    headers = await _super(ac, seed)
    product = seed["p1"]
    product.cost_price = 3
    product.stock_qty = 5
    product.is_active = True
    await db_session.commit()

    val = await ac.get("/api/v1/reports/inventory/valuation", headers=headers)
    assert val.status_code == 200, val.text
    body = val.json()["data"]
    row = next(i for i in body["items"] if i["product_id"] == product.id)
    assert row["quantity"] == pytest.approx(5.0)
    assert row["value"] == pytest.approx(15.0)

    mgr = await _mgr(ac)
    mgr_val = await ac.get("/api/v1/reports/inventory/valuation", headers=mgr)
    assert mgr_val.status_code == 200, mgr_val.text
    assert not any(
        i["product_id"] == product.id and i.get("warehouse_id") is None
        for i in mgr_val.json()["data"]["items"]
    )

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
    assert any("A-1" in line for line in lines)
