"""Out of stock vs low stock, POS warehouse overlay, oversell reject."""

from pathlib import Path

import pytest

from app import models as m
from app.catalog_meta import qty_is_low_stock, qty_is_out_of_stock
from app.dashboard import build_dashboard
from app.reports import inventory_low_stock
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_inventory_and_pos_pages_label_out_of_stock():
    inv = (ROOT / "frontend/app/(dashboard)/inventory/page.tsx").read_text(encoding="utf-8")
    pos = (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")
    lists = (ROOT / "frontend/lib/listPages.ts").read_text(encoding="utf-8")
    assert "Out of stock" in inv
    assert "stockStatusOf" in inv
    assert "oos" in lists
    assert "out of stock at this store" in pos.lower()
    assert "is_out_of_stock" in pos
    assert "Save customer" in pos


@pytest.mark.asyncio
async def test_dashboard_and_low_stock_report_split_oos(db_session, seeded):
    t1 = seeded["t1"].id
    seeded["p1"].stock_qty = 0
    seeded["p1"].reorder_level = 5
    low = m.Product(
        tenant_id=t1,
        name="Near floor",
        sku="A-NEAR",
        cost_price=1,
        selling_price=2,
        stock_qty=1,
        reorder_level=4,
        is_active=True,
    )
    db_session.add(low)
    await db_session.commit()

    dash = await build_dashboard(db_session, t1)
    report = await inventory_low_stock(db_session, t1)
    assert dash["out_of_stock"] >= 1
    assert dash["low_stock"] == report["count"]
    assert report["out_of_stock_count"] == dash["out_of_stock"]
    ids = {row["id"] for row in report["products"]}
    assert seeded["p1"].id not in ids
    assert low.id in ids
    assert qty_is_out_of_stock(0)
    assert not qty_is_low_stock(0, reorder_level=5)


@pytest.mark.asyncio
async def test_pos_search_store_warehouse_zero_and_sale_409(client, db_session, seeded):
    ac, seed = client
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 25
    product.reorder_level = 5
    store = m.Store(tenant_id=tenant_id, name="POS Till", code="POSTILL", is_active=True)
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id,
        store_id=store.id,
        name="POS Till Warehouse",
        code="WH-POSTILL",
        is_active=True,
    )
    db_session.add(wh)
    await db_session.flush()
    db_session.add(
        m.WarehouseStock(
            tenant_id=tenant_id,
            warehouse_id=wh.id,
            product_id=product.id,
            quantity=0,
        )
    )
    await db_session.commit()

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    search = await ac.get(
        f"/api/v1/pos/products/search?store_id={store.id}",
        headers=cashier,
    )
    assert search.status_code == 200, search.text
    hit = next(r for r in search.json()["data"] if r["product_id"] == product.id)
    assert hit["stock_qty"] == 0
    assert hit["is_out_of_stock"] is True
    assert hit["is_low_stock"] is False
    assert hit["stock_status"] == "out"

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        json={"opening_cash": 0, "store_id": store.id},
        headers=cashier,
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
        headers=cashier,
    )
    assert sale.status_code == 409, sale.text
    detail = sale.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "INSUFFICIENT_WAREHOUSE_STOCK"
        assert "out of stock" in str(detail.get("message") or "").lower()
    else:
        assert "stock" in str(detail).lower()
