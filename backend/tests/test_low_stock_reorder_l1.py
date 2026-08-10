"""Stage 17 L1: low-stock traffic lights + suggested_order_qty + reorder-PO."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_low_stock_traffic_lights_suggested_qty_and_reorder_po(client, db_session):
    """PATCH thresholds → product list status → low-stock list → draft reorder PO."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    product = m.Product(
        tenant_id=tenant_id,
        name="S17 L1 Reorder SKU",
        sku="S17-L1-REO",
        cost_price=4.5,
        selling_price=9.0,
        stock_qty=15,
        minimum_stock=0,
        reorder_level=0,
    )
    supplier = m.Party(
        tenant_id=tenant_id,
        name="S17 L1 Supplier",
        kind="supplier",
        credit_limit=0,
    )
    db_session.add_all([product, supplier])
    await db_session.commit()
    product_id, supplier_id = product.id, supplier.id
    foreign_supplier_id = seed["supplier2"].id

    patched = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"minimum_stock": 5, "reorder_level": 20},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()["data"]
    assert float(body["minimum_stock"]) == 5
    assert float(body["reorder_level"]) == 20
    assert body["stock_status"] == "yellow"

    listed = await ac.get("/api/v1/products", headers=headers)
    assert listed.status_code == 200, listed.text
    row = next(p for p in listed.json()["data"] if p["id"] == product_id)
    assert row["stock_status"] == "yellow"

    low = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    assert low.status_code == 200, low.text
    match = next(
        r for r in low.json()["data"] if r["id"] == product_id and r.get("scope") == "product"
    )
    assert match["stock_status"] == "yellow"
    assert float(match["suggested_order_qty"]) == pytest.approx(5.0)  # 20 - 15

    product_row = await db_session.get(m.Product, product_id)
    product_row.stock_qty = 3
    await db_session.commit()

    low_red = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    match_red = next(
        r for r in low_red.json()["data"] if r["id"] == product_id and r.get("scope") == "product"
    )
    assert match_red["stock_status"] == "red"
    suggested = float(match_red["suggested_order_qty"])
    assert suggested == pytest.approx(17.0)  # 20 - 3

    created = await ac.post(
        "/api/v1/inventory/low-stock/reorder-po",
        headers=headers,
        json={"product_id": product_id, "supplier_id": supplier_id},
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    assert po["status"] == "draft"
    assert po["supplier_id"] == supplier_id
    assert "low stock" in (po.get("notes") or "").lower() or "S17-L1-REO" in (po.get("notes") or "")
    line = next(i for i in po["items"] if i["product_id"] == product_id)
    assert float(line["quantity"]) == pytest.approx(suggested)
    assert float(line["unit_price"]) == pytest.approx(4.5)

    db_session.expire_all()
    audit = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == tenant_id,
                m.AuditLog.action == "low_stock_reorder_po",
                m.AuditLog.entity_id == po["id"],
            )
        )
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.module == "inventory"

    foreign = await ac.post(
        "/api/v1/inventory/low-stock/reorder-po",
        headers=headers,
        json={"product_id": product_id, "supplier_id": foreign_supplier_id},
    )
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_warehouse_low_stock_suggested_uses_reorder_qty(client, db_session):
    """Warehouse-scoped thresholds (store reorder policy) appear on low-stock with reorder_qty."""
    ac, seed = client
    headers = await _mgr(ac)
    tenant_id = seed["t1"].id

    product = m.Product(
        tenant_id=tenant_id,
        name="S17 L1 WH Low SKU",
        sku="S17-L1-WH",
        cost_price=2,
        selling_price=4,
        stock_qty=0,
        minimum_stock=0,
        reorder_level=0,
    )
    store = m.Store(tenant_id=tenant_id, name="S17 L1 Store", code="S17L1S", is_active=True)
    db_session.add_all([product, store])
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id,
        store_id=store.id,
        name="S17 L1 Store WH",
        code="S17L1WH",
    )
    db_session.add(wh)
    await db_session.commit()
    product_id, store_id, wh_id = product.id, store.id, wh.id

    stock_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product_id, "quantity": 4, "warehouse_id": wh_id},
    )
    assert stock_in.status_code == 200, stock_in.text

    policy = await ac.put(
        f"/api/v1/stores/{store_id}/reorder-policy",
        headers=headers,
        json={
            "product_id": product_id,
            "minimum_stock": 10,
            "reorder_level": 20,
            "reorder_qty": 40,
        },
    )
    assert policy.status_code == 200, policy.text
    assert policy.json()["data"]["stock_status"] == "red"
    assert float(policy.json()["data"]["reorder_qty"]) == 40

    low = await ac.get("/api/v1/inventory/low-stock", headers=headers)
    assert low.status_code == 200, low.text
    wh_row = next(
        r
        for r in low.json()["data"]
        if r.get("scope") == "warehouse"
        and r.get("warehouse_id") == wh_id
        and r["id"] == product_id
    )
    assert wh_row["stock_status"] == "red"
    assert float(wh_row["minimum_stock"]) == 10
    assert float(wh_row["reorder_level"]) == 20
    assert float(wh_row["suggested_order_qty"]) == pytest.approx(40.0)

    grid = await ac.get(f"/api/v1/products/{product_id}/warehouse-stock", headers=headers)
    assert grid.status_code == 200, grid.text
    wh_grid = next(r for r in grid.json()["data"]["warehouses"] if r["warehouse_id"] == wh_id)
    assert wh_grid["stock_status"] == "red"
    assert float(wh_grid["reorder_qty"]) == 40


def test_inventory_ui_surfaces_low_stock_reorder():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "/inventory/low-stock" in page
    assert "/inventory/low-stock/reorder-po" in page
    assert "'lowstock'" in page or "lowstock" in page
    assert "Create draft PO" in page
    assert "suggested_order_qty" in page or "Suggested" in page
    assert "statusColor" in page
    assert "stock_status" in page


def test_low_stock_reorder_l1_docs():
    plan = (ROOT / "docs/STAGE_17_PLAN.md").read_text(encoding="utf-8")
    assert "| **L1**" in plan
    assert "test_low_stock_reorder_l1.py" in plan
    assert "COMPLETE" in plan
    br = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Stage 17 L1" in br
    assert "[x] Visual indicators on product list" in br or "[x] Visual indicators" in br
    assert "[x] Generate purchase suggestions" in br
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Stage 17 L1" in api
    assert "/inventory/low-stock/reorder-po" in api
