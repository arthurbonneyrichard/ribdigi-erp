"""Retail / wholesale trade channels, MOQ, tiers, reserved POS, Rx report."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.inventory import apply_warehouse_stock_change
from app.packages import canonicalize_industry
from app.stores import create_store, warehouse_for_store
from app.tenants import VALID_INDUSTRIES, normalize_industry
from app.trade import PROVISION_INDUSTRIES, default_sales_channel
from tests.conftest import auth_headers, set_tenant_industry


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_retail_wholesale_is_canonical_and_provisioned():
    assert "retail_wholesale" in VALID_INDUSTRIES
    assert canonicalize_industry("Retail + Wholesale") == "retail_wholesale"
    assert canonicalize_industry("retail+wholesale") == "retail_wholesale"
    assert normalize_industry("RETAIL_WHOLESALE") == "retail_wholesale"
    assert PROVISION_INDUSTRIES == ("retail", "pharmacy", "wholesale", "retail_wholesale")
    assert default_sales_channel("retail_wholesale", source="pos") == "retail"
    assert default_sales_channel("retail_wholesale", source="order") == "wholesale"
    assert default_sales_channel("wholesale", source="pos") == "wholesale"
    assert default_sales_channel("wholesale", source="invoice") == "wholesale"
    assert default_sales_channel("retail_wholesale", source="invoice") == "wholesale"
    assert default_sales_channel("retail", source="invoice") == "retail"
    assert default_sales_channel("pharmacy", source="pos") == "retail"


@pytest.mark.asyncio
async def test_wholesale_and_combo_deny_hotel_fmcg(client, db_session, seeded):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "wholesale")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200
    assert me.json()["data"]["industry"] == "wholesale"
    assert "hotel" not in me.json()["data"]["enabled_modules"]
    assert "fmcg" not in me.json()["data"]["enabled_modules"]
    hotel = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert hotel.status_code == 403
    fmcg = await ac.get("/api/v1/fmcg/schemes", headers=admin)
    assert fmcg.status_code == 403

    await set_tenant_industry(db_session, seed["t1"], "retail_wholesale")
    combo = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dash = await ac.get("/api/v1/dashboard", headers=combo)
    assert dash.status_code == 200, dash.text
    ids = {row["id"] for row in dash.json()["data"]["industry_features"]}
    assert "pos" not in ids
    assert "inventory" not in ids
    assert "quotes" in ids
    assert "orders" in ids
    hrefs = [row["href"] for row in dash.json()["data"]["industry_features"]]
    assert all(not h.startswith("/hotel") for h in hrefs)
    assert all(not h.startswith("/prescriptions") for h in hrefs)


@pytest.mark.asyncio
async def test_wholesale_moq_and_price_tier_on_order(client, db_session, seeded):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "wholesale")
    admin = await _super(ac, seed)
    product_id = seed["p1"].id
    patched = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=admin,
        json={"min_order_qty": 12, "selling_price": 10},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["min_order_qty"] == 12

    tier = await ac.post(
        f"/api/v1/products/{product_id}/price-tiers",
        headers=admin,
        json={"min_qty": 12, "unit_price": 8},
    )
    assert tier.status_code == 200, tier.text

    too_small = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": product_id, "quantity": 2}],
        },
    )
    assert too_small.status_code == 409, too_small.text
    detail = too_small.json()["detail"]
    assert detail["code"] == "MOQ_NOT_MET"

    ok = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": product_id, "quantity": 12}],
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["sales_channel"] == "wholesale"
    assert body["items"][0]["unit_price"] == 8
    assert body["items"][0]["quantity"] == 12


@pytest.mark.asyncio
async def test_combo_pos_is_retail_orders_wholesale(client, db_session, seeded):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "retail_wholesale")
    admin = await _super(ac, seed)
    quote = await ac.post(
        "/api/v1/sales/quotations",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 3, "unit_price": 5}],
        },
    )
    assert quote.status_code == 200, quote.text
    assert quote.json()["data"]["sales_channel"] == "wholesale"

    retail_quote = await ac.post(
        "/api/v1/sales/quotations",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "sales_channel": "retail",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert retail_quote.status_code == 409, retail_quote.text

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post("/api/v1/pos/sessions/open", json={"opening_cash": 0}, headers=cashier)
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = float(product.stock_qty or 0) + 5
    await db_session.commit()
    sale = await ac.post(
        "/api/v1/pos/sales",
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
        headers=cashier,
    )
    assert sale.status_code == 200, sale.text
    sale_data = sale.json()["data"]
    assert sale_data.get("sales_channel") == "retail"


@pytest.mark.asyncio
async def test_pos_cannot_oversell_reserved_qty(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Reserve POS", code="RPOS"
    )
    await db_session.commit()
    wh = await warehouse_for_store(db_session, seed["t1"].id, store.id)
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 4
    await apply_warehouse_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        warehouse_id=wh.id,
        product_id=seed["p1"].id,
        quantity_delta=4,
    )
    await db_session.commit()

    order = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "store_id": store.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 4, "unit_price": 5}],
        },
    )
    assert order.status_code == 200, order.text
    oid = order.json()["data"]["id"]
    conf = await ac.post(f"/api/v1/sales/orders/{oid}/confirm", headers=admin, json={})
    assert conf.status_code == 200, conf.text

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        json={"opening_cash": 0, "store_id": store.id},
        headers=admin,
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]
    blocked = await ac.post(
        "/api/v1/pos/sales",
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
        headers=admin,
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    if isinstance(detail, dict):
        assert detail.get("code") == "INSUFFICIENT_AVAILABLE_STOCK"


@pytest.mark.asyncio
async def test_partial_fulfill_and_delivery_note(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Fill Store", code="FILL"
    )
    await db_session.commit()
    wh = await warehouse_for_store(db_session, seed["t1"].id, store.id)
    product = await db_session.get(m.Product, seed["p1"].id)
    product.stock_qty = 10
    await apply_warehouse_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        warehouse_id=wh.id,
        product_id=seed["p1"].id,
        quantity_delta=10,
    )
    await db_session.commit()
    created = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "store_id": store.id,
            "items": [{"product_id": seed["p1"].id, "quantity": 6, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    oid = created.json()["data"]["id"]
    conf = await ac.post(f"/api/v1/sales/orders/{oid}/confirm", headers=admin, json={})
    assert conf.status_code == 200, conf.text
    fill = await ac.post(
        f"/api/v1/sales/orders/{oid}/fulfill",
        headers=admin,
        json={"items": [{"product_id": seed["p1"].id, "quantity": 2}]},
    )
    assert fill.status_code == 200, fill.text
    assert fill.json()["data"]["status"] == "processing"
    assert fill.json()["data"]["items"][0]["qty_fulfilled"] == 2
    await db_session.refresh(product)
    assert float(product.stock_qty) == 8

    over = await ac.post(
        f"/api/v1/sales/orders/{oid}/fulfill",
        headers=admin,
        json={"items": [{"product_id": seed["p1"].id, "quantity": 9}]},
    )
    assert over.status_code == 409, over.text

    shipped = await ac.post(f"/api/v1/sales/orders/{oid}/ship", headers=admin, json={})
    assert shipped.status_code == 200, shipped.text
    assert shipped.json()["data"]["delivery_note_number"].startswith("DN-")
    assert shipped.json()["data"]["status"] == "shipped"


@pytest.mark.asyncio
async def test_pharmacy_rx_activity_report(client, db_session, seeded):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "pharmacy")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/pharmacy/prescriptions",
        headers=admin,
        json={"items": [{"product_id": seed["p1"].id, "quantity": 3}]},
    )
    assert created.status_code == 200, created.text
    report = await ac.get("/api/v1/reports/pharmacy/rx-activity", headers=admin)
    assert report.status_code == 200, report.text
    data = report.json()["data"]
    assert data["counts"]["total"] >= 1
    assert data["qty_prescribed"] >= 3
    expiry = await ac.get("/api/v1/reports/inventory/expiry?days=30", headers=admin)
    assert expiry.status_code == 200, expiry.text

    await set_tenant_industry(db_session, seed["t1"], "retail")
    retail = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/reports/pharmacy/rx-activity", headers=retail)
    assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
async def test_wholesale_price_preview_and_invoice_follow_qty_tier(client, db_session, seeded):
    """Desk preview and a direct invoice use the same qty break as a sales order."""
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "wholesale")
    admin = await _super(ac, seed)
    product_id = seed["p1"].id
    patched = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=admin,
        json={"min_order_qty": 12, "selling_price": 10},
    )
    assert patched.status_code == 200, patched.text
    tier = await ac.post(
        f"/api/v1/products/{product_id}/price-tiers",
        headers=admin,
        json={"min_qty": 12, "unit_price": 8},
    )
    assert tier.status_code == 200, tier.text

    below = await ac.get(
        f"/api/v1/products/{product_id}/price",
        headers=admin,
        params={"quantity": 2, "sales_channel": "wholesale"},
    )
    assert below.status_code == 200, below.text
    assert below.json()["data"]["unit_price"] == 10
    assert below.json()["data"]["sales_channel"] == "wholesale"

    preview = await ac.get(
        f"/api/v1/products/{product_id}/price",
        headers=admin,
        params={"quantity": 12, "sales_channel": "wholesale"},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["data"]["unit_price"] == 8

    quote = await ac.post(
        "/api/v1/sales/quotations",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": product_id, "quantity": 12}],
        },
    )
    assert quote.status_code == 200, quote.text
    assert quote.json()["data"]["items"][0]["unit_price"] == 8

    short_invoice = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": product_id, "quantity": 2}],
        },
    )
    assert short_invoice.status_code == 409, short_invoice.text
    assert short_invoice.json()["detail"]["code"] == "MOQ_NOT_MET"

    invoice = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": product_id, "quantity": 12}],
        },
    )
    assert invoice.status_code == 200, invoice.text
    body = invoice.json()["data"]
    assert body["sales_channel"] == "wholesale"
    assert body["items"][0]["unit_price"] == 8

    retail_channel = await ac.get(
        f"/api/v1/products/{product_id}/price",
        headers=admin,
        params={"quantity": 12, "sales_channel": "retail"},
    )
    assert retail_channel.status_code == 409, retail_channel.text
