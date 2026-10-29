"""Retail POS + inventory gaps: session location, credit RBAC, audit, profit, zeros."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_inventory_and_reports_tables_product_before_sku():
    inv = (ROOT / "frontend/app/(dashboard)/inventory/page.tsx").read_text(encoding="utf-8")
    reports = (ROOT / "frontend/app/(dashboard)/reports/page.tsx").read_text(encoding="utf-8")
    pos = (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")
    assert "hotelOps ? 'Supply' : restaurantOps ? 'Ingredient' : 'Product'" in inv
    assert inv.index("hotelOps ? 'Supply' : restaurantOps ? 'Ingredient' : 'Product'") < inv.index("<th>SKU</th>")
    assert reports.index("<th>Product</th>") < reports.index("<th>SKU</th>")
    assert "canWriteCredit" in pos
    assert "credit:write" not in pos or "canCreditSale" in pos


@pytest.mark.asyncio
async def test_me_exposes_session_store_scope(client):
    ac, _seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=cashier)
    assert me.status_code == 200, me.text
    data = me.json()["data"]
    assert data.get("store_scope") == "all"
    assert data.get("store_ids") is None
    assert "permissions" in data


@pytest.mark.asyncio
async def test_pos_search_uses_open_session_store_not_client_store(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    product = seed["p1"]
    product.stock_qty = 25
    store = m.Store(tenant_id=tenant_id, name="Session Till", code="SESS1", is_active=True)
    other = m.Store(tenant_id=tenant_id, name="Other Till", code="SESS2", is_active=True)
    db_session.add_all([store, other])
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id,
        store_id=store.id,
        name="Session WH",
        code="WH-SESS1",
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
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        json={"opening_cash": 0, "store_id": store.id},
        headers=cashier,
    )
    assert opened.status_code == 200, opened.text

    search = await ac.get(
        f"/api/v1/pos/products/search?store_id={other.id}",
        headers=cashier,
    )
    assert search.status_code == 200, search.text
    hit = next(r for r in search.json()["data"] if r["product_id"] == product.id)
    assert hit["stock_qty"] == 0
    assert hit["is_out_of_stock"] is True


@pytest.mark.asyncio
async def test_cashier_credit_sale_requires_credit_write(client, db_session):
    ac, seed = client
    from app.rbac import permissions_for_role

    cashier_user = seed["u1"]
    cashier_user.permissions = {**permissions_for_role("cashier"), "credit": []}
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    await db_session.commit()
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        json={"opening_cash": 0},
        headers=cashier,
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        json={
            "session_id": session_id,
            "payment_method": "credit",
            "party_id": seed["party1"].id,
            "items": [{"product_id": product.id, "quantity": 1}],
        },
        headers=cashier,
    )
    assert sale.status_code == 403, sale.text
    assert "credit:write" in str(sale.json().get("detail") or "")


@pytest.mark.asyncio
async def test_pos_checkout_and_discount_are_audited(client, db_session):
    ac, seed = client
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    await db_session.commit()
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        json={"opening_cash": 0},
        headers=mgr,
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "discount_amount": 0.25,
            "discount_type": "fixed",
            "items": [{"product_id": product.id, "quantity": 1}],
        },
        headers=mgr,
    )
    assert sale.status_code == 200, sale.text
    sale_id = sale.json()["data"]["id"]
    tenant_id = seed["t1"].id
    db_session.expire_all()
    actions = {
        row.action
        for row in (
            await db_session.execute(
                select(m.AuditLog).where(
                    m.AuditLog.tenant_id == tenant_id,
                    m.AuditLog.entity_id == sale_id,
                    m.AuditLog.module == "pos",
                )
            )
        ).scalars().all()
    }
    assert "pos_checkout" in actions
    assert "pos_discount" in actions


@pytest.mark.asyncio
async def test_sales_products_name_before_sku_and_profit(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/reports/sales/products", headers=admin)
    assert r.status_code == 200, r.text
    payload = r.json()["data"]
    assert "total_profit" in payload
    rows = payload.get("products") or []
    if rows:
        keys = list(rows[0].keys())
        assert keys.index("name") < keys.index("sku")
        assert "profit" in rows[0]
        assert "cost" in rows[0]


@pytest.mark.asyncio
async def test_inventory_balance_missing_row_is_qty_zero(client, db_session):
    ac, seed = client
    tenant_id = seed["t1"].id
    extra = m.Product(
        tenant_id=tenant_id,
        name="No Balance Row",
        sku="NO-BAL-1",
        cost_price=3,
        selling_price=5,
        stock_qty=0,
        is_active=True,
    )
    db_session.add(extra)
    store = m.Store(tenant_id=tenant_id, name="Bal Store", code="BAL1", is_active=True)
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=tenant_id,
        store_id=store.id,
        name="Bal WH",
        code="WH-BAL1",
        is_active=True,
    )
    db_session.add(wh)
    await db_session.commit()
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.get(
        f"/api/v1/reports/inventory/balance?store_id={store.id}",
        headers=admin,
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]["items"]
    by_id = {i["product_id"]: i for i in items}
    assert extra.id in by_id
    assert float(by_id[extra.id]["quantity"]) == 0
    keys = list(by_id[extra.id].keys())
    assert keys.index("name") < keys.index("sku")


@pytest.mark.asyncio
async def test_product_qr_png_and_label_include_qr(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product = seed["p1"]
    png = await ac.get(f"/api/v1/products/{product.id}/qr.png", headers=admin)
    assert png.status_code == 200, png.text
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"
    label = await ac.get(f"/api/v1/products/{product.id}/barcode/label", headers=admin)
    assert label.status_code == 200, label.text
    body = label.text
    assert "alt=\"qr\"" in body
    assert "SKU" in body
    assert product.name in body
