"""Tenant ecommerce: domains, isolation, cart, reservations, webhooks, Woo, packages."""

from __future__ import annotations

import hashlib
import hmac
import io
import json
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image

import pytest
from sqlalchemy import select

from fastapi import HTTPException

from app import ecommerce as ecom
from app import ecommerce_connectors as connectors_svc
from app import models as m
from app.inventory import get_or_create_warehouse_stock
from app.packages import PACKAGEABLE_MODULES, module_allowed
from tests.conftest import auth_headers, platform_owner_headers

ROOT = Path(__file__).resolve().parents[2]


async def _login_admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _login_cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _login_beta(ac):
    return await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")


async def _seed_storefront(db, seed, *, publish=True, buffer=2, stock=20):
    tenant = seed["t1"]
    product = seed["p1"]
    product.stock_qty = stock
    store = m.Store(tenant_id=tenant.id, name="Web Store", code="WEB1", is_active=True)
    db.add(store)
    await db.flush()
    warehouse = m.Warehouse(
        tenant_id=tenant.id, store_id=store.id, name="Web WH", code="WH-WEB", is_active=True
    )
    db.add(warehouse)
    await db.flush()
    row = await get_or_create_warehouse_stock(
        db, tenant_id=tenant.id, warehouse_id=warehouse.id, product_id=product.id
    )
    row.quantity = stock
    storefront = await ecom.require_storefront(db, tenant.id)
    storefront.is_enabled = True
    storefront.fulfillment_warehouse_id = warehouse.id
    storefront.fulfillment_store_id = store.id
    storefront.allow_delivery = True
    storefront.allow_pickup = True
    if publish:
        await ecom.upsert_listing(
            db,
            tenant=tenant,
            product_id=product.id,
            is_published=True,
            online_price=5,
            stock_buffer=buffer,
        )
    await db.commit()
    return storefront, warehouse, store


@pytest.mark.asyncio
async def test_package_and_role_gates(client, db_session, seeded):
    ac, seed = client
    tenant = seed["t1"]
    assert "ecommerce" in PACKAGEABLE_MODULES
    assert module_allowed(tenant, "ecommerce") is True

    tenant.package_code = "starter"
    tenant.enabled_modules = None
    await db_session.commit()
    admin = await _login_admin(ac)
    blocked = await ac.get("/api/v1/ecommerce", headers=admin)
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["detail"]["code"] == "PACKAGE_FEATURE_DISABLED"

    tenant.package_code = "professional"
    tenant.industry = "hotel"
    await db_session.commit()
    hotel_admin = await _login_admin(ac)
    hotel = await ac.get("/api/v1/ecommerce", headers=hotel_admin)
    assert hotel.status_code == 403, hotel.text

    tenant.industry = "retail"
    await db_session.commit()
    cashier = await _login_cashier(ac)
    denied = await ac.get("/api/v1/ecommerce", headers=cashier)
    assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
async def test_domains_unique_verify_and_unknown_host(client, db_session, seeded):
    ac, seed = client
    admin = await _login_admin(ac)
    added = await ac.post(
        "/api/v1/ecommerce/domains",
        headers=admin,
        json={"hostname": "Shop.Alpha.test"},
    )
    assert added.status_code == 200, added.text
    domain = added.json()["data"]
    assert domain["hostname"] == "shop.alpha.test"
    assert domain["status"] == "pending"
    token = domain["verification_token"]

    taken = await ac.post(
        "/api/v1/ecommerce/domains",
        headers=admin,
        json={"hostname": "shop.alpha.test"},
    )
    assert taken.status_code == 200
    too_soon = await ac.post(f"/api/v1/ecommerce/domains/{domain['id']}/https-ready", headers=admin)
    assert too_soon.status_code == 400, too_soon.text

    ecom.set_dns_lookup(lambda host: [f"ribdigi-site={token}"])
    try:
        verified = await ac.post(f"/api/v1/ecommerce/domains/{domain['id']}/verify", headers=admin)
        assert verified.status_code == 200, verified.text
        assert verified.json()["data"]["status"] == "verified"
        ready = await ac.post(f"/api/v1/ecommerce/domains/{domain['id']}/https-ready", headers=admin)
        assert ready.status_code == 200
        assert ready.json()["data"]["https_ready"] is True
    finally:
        ecom.set_dns_lookup(None)

    unknown = await ac.get("/api/v1/storefront/bootstrap", headers={"Host": "unknown.example"})
    assert unknown.status_code == 404, unknown.text
    assert unknown.json()["detail"]["code"] == "STOREFRONT_HOST_UNKNOWN"

    await _seed_storefront(db_session, seed)
    opened = await ac.get("/api/v1/storefront/bootstrap", headers={"Host": "shop.alpha.test"})
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["storefront"]["company_name"] == "Alpha Co"
    assert "preview_token" not in opened.json()["data"]["storefront"]


@pytest.mark.asyncio
async def test_domain_isolation_between_tenants(client, db_session, seeded):
    ac, seed = client
    admin = await _login_admin(ac)
    first = await ac.post(
        "/api/v1/ecommerce/domains",
        headers=admin,
        json={"hostname": "only-alpha.test"},
    )
    assert first.status_code == 200, first.text
    with pytest.raises(HTTPException) as clash:
        await ecom.add_domain(db_session, tenant=seed["t2"], hostname="only-alpha.test")
    assert clash.value.status_code == 409

    beta = await _login_beta(ac)
    denied = await ac.get("/api/v1/ecommerce", headers=beta)
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_catalog_is_opt_in(client, db_session, seeded):
    ac, seed = client
    storefront, _wh, _store = await _seed_storefront(db_session, seed, publish=False)
    preview = storefront.preview_token
    catalog = await ac.get(f"/api/v1/storefront/bootstrap?preview_token={preview}")
    assert catalog.status_code == 200, catalog.text
    assert catalog.json()["data"]["catalog"] == []

    admin = await _login_admin(ac)
    published = await ac.put(
        "/api/v1/ecommerce/listings",
        headers=admin,
        json={"product_id": seed["p1"].id, "is_published": True, "online_price": 9, "stock_buffer": 1},
    )
    assert published.status_code == 200, published.text
    again = await ac.get(f"/api/v1/storefront/bootstrap?preview_token={preview}")
    items = again.json()["data"]["catalog"]
    assert len(items) == 1
    assert items[0]["price"] == 9
    assert items[0]["product_id"] == seed["p1"].id


@pytest.mark.asyncio
async def test_cart_checkout_reservation_and_return_does_not_pay(client, db_session, seeded):
    ac, seed = client
    storefront, warehouse, _store = await _seed_storefront(db_session, seed, buffer=2, stock=10)
    preview = storefront.preview_token
    cart = await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")
    assert cart.status_code == 200, cart.text
    token = cart.json()["data"]["token"]

    added = await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 3},
    )
    assert added.status_code == 200, added.text
    assert added.json()["data"]["subtotal"] == 15

    too_many = await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 9},
    )
    assert too_many.status_code == 409, too_many.text

    checkout = await ac.post(
        f"/api/v1/storefront/checkout?preview_token={preview}",
        json={
            "cart_token": token,
            "guest_name": "Ama Guest",
            "guest_email": "ama@example.com",
            "fulfillment": "delivery",
            "delivery_address": "12 Market Street Accra",
        },
    )
    assert checkout.status_code == 200, checkout.text
    order = checkout.json()["data"]
    assert order["status"] == "awaiting_payment"
    assert order["paid"] is False
    assert order["payment"]["paid"] is False
    tracking = order["tracking_token"]
    await db_session.commit()

    reserved = (
        await db_session.execute(
            select(m.EcommerceReservation).where(m.EcommerceReservation.order_id == order["id"])
        )
    ).scalars().all()
    assert len(reserved) == 1
    assert float(reserved[0].quantity) == 3

    from app.reservations import available_qty

    avail = await available_qty(
        db_session,
        tenant_id=seed["t1"].id,
        warehouse_id=warehouse.id,
        product_id=seed["p1"].id,
    )
    assert avail == 7

    bounced = await ac.get(f"/api/v1/storefront/orders/{tracking}/return?preview_token={preview}")
    assert bounced.status_code == 200, bounced.text
    assert bounced.json()["data"]["return_marks_paid"] is False
    assert bounced.json()["data"]["paid"] is False

    track = await ac.get(f"/api/v1/storefront/orders/{tracking}?preview_token={preview}")
    assert track.json()["data"]["status"] == "awaiting_payment"


@pytest.mark.asyncio
async def test_cancel_releases_reservation(client, db_session, seeded):
    ac, seed = client
    storefront, warehouse, _store = await _seed_storefront(db_session, seed, buffer=0, stock=8)
    preview = storefront.preview_token
    cart = await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")
    token = cart.json()["data"]["token"]
    await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 4},
    )
    checkout = await ac.post(
        f"/api/v1/storefront/checkout?preview_token={preview}",
        json={
            "cart_token": token,
            "guest_name": "Kofi Guest",
            "fulfillment": "pickup",
        },
    )
    assert checkout.status_code == 200, checkout.text
    order_id = checkout.json()["data"]["id"]
    admin = await _login_admin(ac)
    cancelled = await ac.post(f"/api/v1/ecommerce/orders/{order_id}/cancel", headers=admin)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == "cancelled"
    from app.reservations import available_qty

    avail = await available_qty(
        db_session, tenant_id=seed["t1"].id, warehouse_id=warehouse.id, product_id=seed["p1"].id
    )
    assert avail == 8


@pytest.mark.asyncio
async def test_expiry_releases_reservation(db_session, seeded):
    storefront, warehouse, _store = await _seed_storefront(db_session, seeded, buffer=0, stock=6)
    cart = await ecom.create_cart(db_session, seeded["t1"].id)
    await ecom.set_cart_item(
        db_session,
        tenant=seeded["t1"],
        storefront=storefront,
        cart=cart,
        product_id=seeded["p1"].id,
        quantity=2,
    )
    order = await ecom.checkout(
        db_session,
        tenant=seeded["t1"],
        storefront=storefront,
        cart=cart,
        guest_name="Expired Guest",
        guest_email=None,
        guest_phone=None,
        fulfillment="pickup",
        delivery_address=None,
        notes=None,
    )
    order.reserved_until = datetime.utcnow() - timedelta(minutes=1)
    await db_session.flush()
    expired = await ecom.expire_due_reservations(db_session, seeded["t1"].id)
    await db_session.commit()
    assert expired == 1
    await db_session.refresh(order)
    assert order.status == "expired"
    from app.reservations import available_qty

    avail = await available_qty(
        db_session, tenant_id=seeded["t1"].id, warehouse_id=warehouse.id, product_id=seeded["p1"].id
    )
    assert avail == 6


@pytest.mark.asyncio
async def test_signed_webhook_pays_once_and_posts_invoice(client, db_session, seeded):
    ac, seed = client
    storefront, _warehouse, _store = await _seed_storefront(db_session, seed, buffer=0, stock=10)
    admin = await _login_admin(ac)
    saved = await ac.patch(
        "/api/v1/ecommerce/gateway",
        headers=admin,
        json={"provider": "mock", "mode": "test", "secret": "test_storefront_sk", "webhook_secret": "hook_secret"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["secret_configured"] is True
    assert "test_storefront_sk" not in saved.text

    preview = storefront.preview_token
    cart = await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")
    token = cart.json()["data"]["token"]
    await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 2},
    )
    checkout = await ac.post(
        f"/api/v1/storefront/checkout?preview_token={preview}",
        json={"cart_token": token, "guest_name": "Paid Guest", "fulfillment": "pickup"},
    )
    assert checkout.status_code == 200, checkout.text
    reference = checkout.json()["data"]["payment"]["reference"]
    amount = checkout.json()["data"]["total_amount"]
    body = json.dumps(
        {"event_id": "evt_1", "reference": reference, "amount": amount, "currency": "GHS"}
    ).encode()
    signature = hmac.new(b"hook_secret", body, hashlib.sha512).hexdigest()
    paid = await ac.post(
        f"/api/v1/storefront/payments/webhook/mock?preview_token={preview}",
        content=body,
        headers={"X-Ribdigi-Signature": signature, "Content-Type": "application/json"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["paid"] is True

    replay = await ac.post(
        f"/api/v1/storefront/payments/webhook/mock?preview_token={preview}",
        content=body,
        headers={"X-Ribdigi-Signature": signature, "Content-Type": "application/json"},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"]["idempotent"] is True

    order_id = checkout.json()["data"]["id"]
    await db_session.commit()
    order = await db_session.get(m.EcommerceOrder, order_id)
    assert order.status == "paid"
    assert order.sales_invoice_id
    invoices = (
        await db_session.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == seed["t1"].id,
                m.SalesInvoice.id == order.sales_invoice_id,
            )
        )
    ).scalars().all()
    assert len(invoices) == 1

    user = (
        await db_session.execute(select(m.User).where(m.User.email == "ama-paid@example.com"))
    ).scalar_one_or_none()
    assert user is None


@pytest.mark.asyncio
async def test_woocommerce_import_is_unpublished_and_deduped(client, db_session, seeded):
    ac, seed = client
    await _seed_storefront(db_session, seed, publish=False)
    admin = await _login_admin(ac)

    async def fake_get(url, key, secret):
        assert key == "ck_test"
        if "products" in url:
            return [
                {"id": 11, "name": "Woo Mug", "sku": "WOO-MUG", "price": "12.00", "short_description": "Mug"},
                {"id": 11, "name": "Woo Mug again", "sku": "WOO-MUG", "price": "12.00"},
            ]
        return []

    connectors_svc.set_connector_http_get(fake_get)
    try:
        saved = await ac.patch(
            "/api/v1/ecommerce/connectors",
            headers=admin,
            json={
                "platform": "woocommerce",
                "store_url": "https://shop.example.com",
                "consumer_key": "ck_test",
                "consumer_secret": "cs_test",
                "enabled": True,
            },
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["data"]["credentials_configured"] is True
        assert "cs_test" not in saved.text
        connector_id = saved.json()["data"]["id"]
        first = await ac.post(
            f"/api/v1/ecommerce/connectors/{connector_id}/sync",
            headers=admin,
            json={"kind": "products"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["data"]["status"] == "succeeded"
        assert first.json()["data"]["stats"]["linked"] == 1
        second = await ac.post(
            f"/api/v1/ecommerce/connectors/{connector_id}/sync",
            headers=admin,
            json={"kind": "products"},
        )
        assert second.json()["data"]["stats"]["skipped"] >= 1
    finally:
        connectors_svc.set_connector_http_get(None)

    listing = (
        await db_session.execute(
            select(m.EcommerceListing).where(m.EcommerceListing.tenant_id == seed["t1"].id)
        )
    ).scalars().first()
    assert listing is not None
    assert listing.is_published is False

    other = await ac.patch(
        "/api/v1/ecommerce/connectors",
        headers=admin,
        json={"platform": "shopify"},
    )
    assert other.status_code == 501, other.text


async def _checkout(ac, preview, product_id, qty, name="Guest"):
    cart = await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")
    token = cart.json()["data"]["token"]
    await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": product_id, "quantity": qty},
    )
    return await ac.post(
        f"/api/v1/storefront/checkout?preview_token={preview}",
        json={"cart_token": token, "guest_name": name, "fulfillment": "pickup"},
    )


@pytest.mark.asyncio
async def test_forged_webhook_does_not_pay(client, db_session, seeded):
    ac, seed = client
    storefront, _wh, _store = await _seed_storefront(db_session, seed, buffer=0, stock=6)
    admin = await _login_admin(ac)
    await ac.patch(
        "/api/v1/ecommerce/gateway",
        headers=admin,
        json={"provider": "mock", "mode": "test", "secret": "sk", "webhook_secret": "hook_secret"},
    )
    preview = storefront.preview_token
    checkout = await _checkout(ac, preview, seed["p1"].id, 1, "Forge Guest")
    assert checkout.status_code == 200, checkout.text
    body = json.dumps(
        {
            "event_id": "evt_forged",
            "reference": checkout.json()["data"]["payment"]["reference"],
            "amount": checkout.json()["data"]["total_amount"],
            "currency": "GHS",
        }
    ).encode()
    forged = await ac.post(
        f"/api/v1/storefront/payments/webhook/mock?preview_token={preview}",
        content=body,
        headers={"X-Ribdigi-Signature": "deadbeef", "Content-Type": "application/json"},
    )
    assert forged.status_code == 401, forged.text
    track = await ac.get(
        f"/api/v1/storefront/orders/{checkout.json()['data']['tracking_token']}?preview_token={preview}"
    )
    assert track.json()["data"]["status"] == "awaiting_payment"


@pytest.mark.asyncio
async def test_second_checkout_cannot_oversell_reserved_stock(client, db_session, seeded):
    ac, seed = client
    storefront, _wh, _store = await _seed_storefront(db_session, seed, buffer=0, stock=5)
    preview = storefront.preview_token
    first = await _checkout(ac, preview, seed["p1"].id, 4, "First Guest")
    assert first.status_code == 200, first.text
    cart = await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")
    token = cart.json()["data"]["token"]
    second = await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 2},
    )
    assert second.status_code == 409, second.text
    assert second.json()["detail"]["code"] == "INSUFFICIENT_ONLINE_STOCK"


@pytest.mark.asyncio
async def test_domain_reverify_fails_when_txt_removed(client, db_session, seeded):
    ac, seed = client
    admin = await _login_admin(ac)
    added = await ac.post(
        "/api/v1/ecommerce/domains",
        headers=admin,
        json={"hostname": "owned.alpha.test"},
    )
    domain = added.json()["data"]
    token = domain["verification_token"]
    ecom.set_dns_lookup(lambda host: [f"ribdigi-site={token}"])
    try:
        verified = await ac.post(f"/api/v1/ecommerce/domains/{domain['id']}/verify", headers=admin)
        assert verified.status_code == 200
        ecom.set_dns_lookup(lambda host: [])
        lost = await ac.post(f"/api/v1/ecommerce/domains/{domain['id']}/verify", headers=admin)
        assert lost.status_code == 400, lost.text
        assert lost.json()["detail"]["code"] == "DOMAIN_OWNERSHIP_CHANGED"
    finally:
        ecom.set_dns_lookup(None)
    await db_session.commit()
    row = await db_session.get(m.EcommerceDomain, domain["id"])
    assert row.status == "failed"
    assert row.verification_token != token


@pytest.mark.asyncio
async def test_paid_order_fulfillment_return_and_ledger(client, db_session, seeded):
    ac, seed = client
    storefront, warehouse, _store = await _seed_storefront(db_session, seed, buffer=0, stock=10)
    admin = await _login_admin(ac)
    await ac.patch(
        "/api/v1/ecommerce/gateway",
        headers=admin,
        json={"provider": "mock", "mode": "test", "secret": "sk", "webhook_secret": "hook_secret"},
    )
    preview = storefront.preview_token
    checkout = await _checkout(ac, preview, seed["p1"].id, 2, "Ledger Guest")
    assert checkout.status_code == 200, checkout.text
    body = json.dumps(
        {
            "event_id": "evt_ledger",
            "reference": checkout.json()["data"]["payment"]["reference"],
            "amount": checkout.json()["data"]["total_amount"],
            "currency": "GHS",
        }
    ).encode()
    signature = hmac.new(b"hook_secret", body, hashlib.sha512).hexdigest()
    paid = await ac.post(
        f"/api/v1/storefront/payments/webhook/mock?preview_token={preview}",
        content=body,
        headers={"X-Ribdigi-Signature": signature, "Content-Type": "application/json"},
    )
    assert paid.status_code == 200, paid.text
    order_id = checkout.json()["data"]["id"]
    tenant_id = seed["t1"].id
    product_id = seed["p1"].id
    warehouse_id = warehouse.id
    packed = await ac.post(f"/api/v1/ecommerce/orders/{order_id}/fulfill?target=packed", headers=admin)
    assert packed.json()["data"]["status"] == "packed"
    dispatched = await ac.post(
        f"/api/v1/ecommerce/orders/{order_id}/fulfill?target=dispatched", headers=admin
    )
    assert dispatched.json()["data"]["status"] == "dispatched"
    delivered = await ac.post(
        f"/api/v1/ecommerce/orders/{order_id}/fulfill?target=delivered", headers=admin
    )
    assert delivered.json()["data"]["status"] == "delivered"
    invoice_id = delivered.json()["data"]["sales_invoice_id"]
    await db_session.commit()
    db_session.expire_all()
    invoice = await db_session.get(m.SalesInvoice, invoice_id)
    assert invoice is not None
    journals = (
        await db_session.execute(select(m.JournalEntry).where(m.JournalEntry.tenant_id == tenant_id))
    ).scalars().all()
    assert journals
    from app.reservations import available_qty

    after_sale = await available_qty(
        db_session, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    assert after_sale == 8
    returned = await ac.post(f"/api/v1/ecommerce/orders/{order_id}/return", headers=admin)
    assert returned.status_code == 200, returned.text
    assert returned.json()["data"]["status"] == "returned"
    await db_session.commit()
    db_session.expire_all()
    after_return = await available_qty(
        db_session, tenant_id=tenant_id, warehouse_id=warehouse_id, product_id=product_id
    )
    assert after_return == 10


@pytest.mark.asyncio
async def test_woocommerce_orders_are_deduped_and_running_job_is_reused(client, db_session, seeded):
    ac, seed = client
    await _seed_storefront(db_session, seed, publish=False)
    admin = await _login_admin(ac)

    async def fake_get(url, key, secret):
        if "orders" in url:
            return [
                {
                    "id": 88,
                    "currency": "GHS",
                    "total": "10",
                    "billing": {"first_name": "Woo", "last_name": "Buyer", "email": "woo@example.com"},
                    "line_items": [{"sku": seed["p1"].sku, "quantity": 1, "price": 5}],
                },
                {
                    "id": 88,
                    "currency": "GHS",
                    "total": "10",
                    "billing": {"first_name": "Woo", "last_name": "Buyer"},
                    "line_items": [],
                },
            ]
        return []

    connectors_svc.set_connector_http_get(fake_get)
    try:
        saved = await ac.patch(
            "/api/v1/ecommerce/connectors",
            headers=admin,
            json={
                "platform": "woocommerce",
                "store_url": "https://shop.example.com",
                "consumer_key": "ck_test",
                "consumer_secret": "cs_test",
                "enabled": True,
            },
        )
        connector_id = saved.json()["data"]["id"]
        first = await ac.post(
            f"/api/v1/ecommerce/connectors/{connector_id}/sync",
            headers=admin,
            json={"kind": "orders"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["data"]["stats"]["imported"] == 1
        second = await ac.post(
            f"/api/v1/ecommerce/connectors/{connector_id}/sync",
            headers=admin,
            json={"kind": "orders"},
        )
        assert second.json()["data"]["stats"]["skipped"] >= 1
        running = m.EcommerceSyncJob(
            tenant_id=seed["t1"].id,
            connector_id=connector_id,
            kind="orders",
            status="running",
            attempt=1,
            started_at=datetime.utcnow(),
        )
        db_session.add(running)
        await db_session.commit()
        reused = await ac.post(
            f"/api/v1/ecommerce/connectors/{connector_id}/sync",
            headers=admin,
            json={"kind": "orders"},
        )
        assert reused.json()["data"]["id"] == running.id
        assert reused.json()["data"]["status"] == "running"
    finally:
        connectors_svc.set_connector_http_get(None)


@pytest.mark.asyncio
async def test_catalog_search_and_platform_health_redacts_secrets(client, db_session, seeded):
    ac, seed = client
    storefront, _wh, _store = await _seed_storefront(db_session, seed, publish=True)
    preview = storefront.preview_token
    empty = await ac.get(f"/api/v1/storefront/bootstrap?preview_token={preview}&q=zzzz")
    assert empty.json()["data"]["catalog"] == []
    found = await ac.get(f"/api/v1/storefront/bootstrap?preview_token={preview}&q=widget")
    assert len(found.json()["data"]["catalog"]) == 1
    owner = await platform_owner_headers(ac, seed)
    usage = await ac.get(f"/api/v1/tenants/{seed['t1'].slug}/usage", headers=owner)
    assert usage.status_code == 200, usage.text
    health = usage.json()["data"]["ecommerce_health"]
    assert "verification_token" not in str(health)
    assert "secret" not in str(health).lower() or "secret_configured" not in str(health)
    assert "txt_record" not in str(health)
    assert health["entitled"] is True


@pytest.mark.asyncio
async def test_shopper_account_history_is_isolated(client, db_session, seeded):
    ac, seed = client
    storefront, _wh, _store = await _seed_storefront(db_session, seed, buffer=0, stock=6)
    preview = storefront.preview_token
    staff = await ac.post(
        f"/api/v1/storefront/account/register?preview_token={preview}",
        json={"name": "Staff Clash", "email": "admin@alpha.example.com", "password": "Shopper1!"},
    )
    assert staff.status_code == 409, staff.text
    created = await ac.post(
        f"/api/v1/storefront/account/register?preview_token={preview}",
        json={"name": "Ama Shopper", "email": "ama.shopper@example.com", "password": "Shopper1!"},
    )
    assert created.status_code == 200, created.text
    token = created.json()["data"]["session_token"]
    assert token
    cart = await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")
    await ac.post(
        f"/api/v1/storefront/cart/{cart.json()['data']['token']}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 1},
    )
    checkout = await ac.post(
        f"/api/v1/storefront/checkout?preview_token={preview}",
        headers={"X-Storefront-Shopper": token},
        json={"cart_token": cart.json()["data"]["token"], "fulfillment": "pickup"},
    )
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["data"]["shopper_id"] == created.json()["data"]["id"]
    me = await ac.get(
        f"/api/v1/storefront/account/me?preview_token={preview}",
        headers={"X-Storefront-Shopper": token},
    )
    assert me.status_code == 200, me.text
    assert me.json()["data"]["email"] == "ama.shopper@example.com"
    history = await ac.get(
        f"/api/v1/storefront/account/orders?preview_token={preview}",
        headers={"X-Storefront-Shopper": token},
    )
    assert history.status_code == 200, history.text
    assert len(history.json()["data"]["orders"]) == 1
    beta_sf = await ecom.require_storefront(db_session, seed["t2"].id)
    await db_session.commit()
    leaked = await ac.get(
        f"/api/v1/storefront/account/orders?preview_token={beta_sf.preview_token}",
        headers={"X-Storefront-Shopper": token},
    )
    assert leaked.status_code in {401, 403, 404}


@pytest.mark.asyncio
async def test_variant_cart_line_uses_variant_price(client, db_session, seeded):
    ac, seed = client
    storefront, _wh, _store = await _seed_storefront(db_session, seed, buffer=0, stock=8)
    listing = (
        await db_session.execute(
            select(m.EcommerceListing).where(m.EcommerceListing.product_id == seed["p1"].id)
        )
    ).scalar_one()
    listing.online_price = None
    variant = m.ProductVariant(
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        name="Large",
        sku="A-1-LG",
        selling_price=8,
        is_active=True,
    )
    db_session.add(variant)
    await db_session.commit()
    preview = storefront.preview_token
    catalog = await ac.get(f"/api/v1/storefront/bootstrap?preview_token={preview}")
    assert catalog.json()["data"]["catalog"][0]["variants"][0]["id"] == variant.id
    cart = await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")
    token = cart.json()["data"]["token"]
    added = await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 2, "variant_id": variant.id},
    )
    assert added.status_code == 200, added.text
    line = added.json()["data"]["items"][0]
    assert line["variant_id"] == variant.id
    assert line["variant_name"] == "Large"
    assert line["unit_price"] == 8
    assert line["line_total"] == 16
    missing = await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": seed["p1"].id, "quantity": 1, "variant_id": "00000000-0000-0000-0000-000000000099"},
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_woocommerce_outbound_put_on_fulfill(client, db_session, seeded):
    ac, seed = client
    storefront, _wh, _store = await _seed_storefront(db_session, seed, buffer=0, stock=10)
    admin = await _login_admin(ac)
    await ac.patch(
        "/api/v1/ecommerce/gateway",
        headers=admin,
        json={"provider": "mock", "mode": "test", "secret": "sk", "webhook_secret": "hook_secret"},
    )
    saved = await ac.patch(
        "/api/v1/ecommerce/connectors",
        headers=admin,
        json={
            "platform": "woocommerce",
            "store_url": "https://shop.example.com",
            "consumer_key": "ck_out",
            "consumer_secret": "cs_out",
            "enabled": True,
        },
    )
    assert saved.status_code == 200, saved.text
    listing = (
        await db_session.execute(
            select(m.EcommerceListing).where(m.EcommerceListing.product_id == seed["p1"].id)
        )
    ).scalar_one()
    listing.external_id = "woo:11"
    await db_session.commit()
    puts: list[tuple[str, dict]] = []

    async def fake_put(url, key, secret, body):
        puts.append((url, body))
        return {"ok": True}

    connectors_svc.set_connector_http_put(fake_put)
    try:
        preview = storefront.preview_token
        checkout = await _checkout(ac, preview, seed["p1"].id, 1, "Woo Guest")
        assert checkout.status_code == 200, checkout.text
        order_id = checkout.json()["data"]["id"]
        body = json.dumps(
            {
                "event_id": "evt_woo_out",
                "reference": checkout.json()["data"]["payment"]["reference"],
                "amount": checkout.json()["data"]["total_amount"],
                "currency": "GHS",
            }
        ).encode()
        signature = hmac.new(b"hook_secret", body, hashlib.sha512).hexdigest()
        paid = await ac.post(
            f"/api/v1/storefront/payments/webhook/mock?preview_token={preview}",
            content=body,
            headers={"X-Ribdigi-Signature": signature, "Content-Type": "application/json"},
        )
        assert paid.status_code == 200, paid.text
        order = await db_session.get(m.EcommerceOrder, order_id)
        order.external_id = "woo:88"
        await db_session.commit()
        packed = await ac.post(f"/api/v1/ecommerce/orders/{order_id}/fulfill?target=packed", headers=admin)
        assert packed.status_code == 200, packed.text
        assert packed.json()["data"]["status"] == "packed"
        assert any("/orders/88" in url and body.get("status") == "processing" for url, body in puts)
        assert any("/products/11" in url and "stock_quantity" in body for url, body in puts)
    finally:
        connectors_svc.set_connector_http_put(None)


@pytest.mark.asyncio
async def test_website_url_links_and_unlinks(client, db_session, seeded):
    ac, _seed = client
    admin = await _login_admin(ac)
    added = await ac.post(
        "/api/v1/ecommerce/domains",
        headers=admin,
        json={"hostname": "https://www.Linked.Alpha.test/shop"},
    )
    assert added.status_code == 200, added.text
    domain = added.json()["data"]
    assert domain["hostname"] == "linked.alpha.test"
    home = await ac.get("/api/v1/ecommerce", headers=admin)
    assert home.status_code == 200, home.text
    assert "company_website" in home.json()["data"]["storefront"]

    remote_http = await ac.post(
        "/api/v1/ecommerce/domains",
        headers=admin,
        json={"hostname": "http://shop.example.com"},
    )
    assert remote_http.status_code == 422
    reserved = await ac.post(
        "/api/v1/ecommerce/domains",
        headers=admin,
        json={"hostname": "shop.ribdigihouse.com"},
    )
    assert reserved.status_code == 422

    removed = await ac.delete(f"/api/v1/ecommerce/domains/{domain['id']}", headers=admin)
    assert removed.status_code == 200, removed.text
    gone = await ac.get("/api/v1/ecommerce", headers=admin)
    assert all(row["hostname"] != "linked.alpha.test" for row in gone.json()["data"]["domains"])


@pytest.mark.asyncio
async def test_product_bootstrap_and_cart_remove(client, db_session, seeded):
    ac, seed = client
    storefront, _wh, _store = await _seed_storefront(db_session, seed, publish=True)
    preview = storefront.preview_token
    product_id = seed["p1"].id
    one = await ac.get(
        f"/api/v1/storefront/bootstrap?preview_token={preview}&product_id={product_id}"
    )
    assert one.status_code == 200, one.text
    catalog = one.json()["data"]["catalog"]
    assert len(catalog) == 1
    assert catalog[0]["product_id"] == product_id
    missing = await ac.get(
        f"/api/v1/storefront/bootstrap?preview_token={preview}&product_id={'0' * 8}-{'0' * 4}-{'0' * 4}-{'0' * 4}-{'0' * 12}"
    )
    assert missing.status_code == 200, missing.text
    assert missing.json()["data"]["catalog"] == []

    cart = await ac.post(f"/api/v1/storefront/cart?preview_token={preview}")
    token = cart.json()["data"]["token"]
    added = await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": product_id, "quantity": 2},
    )
    assert added.status_code == 200, added.text
    assert added.json()["data"]["items"][0]["quantity"] == 2
    removed = await ac.post(
        f"/api/v1/storefront/cart/{token}/items?preview_token={preview}",
        json={"product_id": product_id, "quantity": 0},
    )
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_storefront_tagline_garbage_is_422(client, db_session, seeded):
    ac, _seed = client
    admin = await _login_admin(ac)
    bad = await ac.patch("/api/v1/ecommerce", headers=admin, json={"tagline": "!!!"})
    assert bad.status_code == 422, bad.text
    url = await ac.patch(
        "/api/v1/ecommerce", headers=admin, json={"tagline": "http://not-a-tagline"}
    )
    assert url.status_code == 422, url.text
    ok = await ac.patch("/api/v1/ecommerce", headers=admin, json={"tagline": "Fresh daily"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["tagline"] == "Fresh daily"
    policy = await ac.patch(
        "/api/v1/ecommerce", headers=admin, json={"policy_shipping": "!!!"}
    )
    assert policy.status_code == 422, policy.text


def _png_bytes() -> bytes:
    img = Image.new("RGB", (32, 32), color=(74, 176, 18))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_storefront_media_and_catalog_honesty(client, db_session, seeded):
    ac, seed = client
    admin = await _login_admin(ac)
    storefront, _wh, _store = await _seed_storefront(db_session, seed, publish=True)
    preview = storefront.preview_token
    tenant_id = seed["t1"].id
    product_id = seed["p1"].id

    missing = await ac.get(f"/api/v1/storefront/media/logo?preview_token={preview}")
    assert missing.status_code == 404, missing.text

    uploaded = await ac.post(
        "/api/v1/ecommerce/media/logo",
        headers=admin,
        files={"file": ("shop-logo.png", _png_bytes(), "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["data"]["has_logo"] is True
    assert "key" not in uploaded.json()["data"] or uploaded.json()["data"].get("uploaded")
    banner = await ac.post(
        "/api/v1/ecommerce/media/banner",
        headers=admin,
        files={"file": ("hero.png", _png_bytes(), "image/png")},
    )
    assert banner.status_code == 200, banner.text
    assert banner.json()["data"]["has_banner"] is True
    icon = await ac.post(
        "/api/v1/ecommerce/media/favicon",
        headers=admin,
        files={"file": ("icon.png", _png_bytes(), "image/png")},
    )
    assert icon.status_code == 200, icon.text
    assert icon.json()["data"]["has_favicon"] is True

    public_logo = await ac.get(f"/api/v1/storefront/media/logo?preview_token={preview}")
    assert public_logo.status_code == 200, public_logo.text
    assert public_logo.headers.get("content-type", "").startswith("image/")
    public_banner = await ac.get(f"/api/v1/storefront/media/banner?preview_token={preview}")
    assert public_banner.status_code == 200
    public_icon = await ac.get(f"/api/v1/storefront/media/favicon?preview_token={preview}")
    assert public_icon.status_code == 200
    unknown_kind = await ac.get(f"/api/v1/storefront/media/hero?preview_token={preview}")
    assert unknown_kind.status_code == 422

    boot = await ac.get(f"/api/v1/storefront/bootstrap?preview_token={preview}")
    meta = boot.json()["data"]["storefront"]
    assert meta["has_logo"] is True
    assert meta["has_banner"] is True
    assert meta["has_favicon"] is True
    assert "logo_url" not in meta
    assert "preview_token" not in meta

    garbage_q = await ac.get(f"/api/v1/storefront/bootstrap?preview_token={preview}&q=!!!")
    assert garbage_q.status_code == 422, garbage_q.text
    url_q = await ac.get(f"/api/v1/storefront/bootstrap?preview_token={preview}&q=http://x")
    assert url_q.status_code == 422, url_q.text
    garbage_preview = await ac.get("/api/v1/storefront/bootstrap?preview_token=!!!")
    assert garbage_preview.status_code == 422, garbage_preview.text
    url_preview = await ac.get("/api/v1/storefront/bootstrap?preview_token=http://x")
    assert url_preview.status_code == 422, url_preview.text
    garbage_login = await ac.post(
        f"/api/v1/storefront/account/login?preview_token={preview}",
        json={"email": "ama.shopper@example.com", "password": "!!!"},
    )
    assert garbage_login.status_code == 422, garbage_login.text

    unpublished_image = await ac.get(
        f"/api/v1/storefront/products/{product_id}/image?preview_token={preview}"
    )
    assert unpublished_image.status_code == 404

    from sqlalchemy import update

    logo_key = (
        await db_session.execute(
            select(m.EcommerceStorefront.logo_url).where(m.EcommerceStorefront.tenant_id == tenant_id)
        )
    ).scalar_one()
    assert logo_key
    await db_session.execute(update(m.Product).where(m.Product.id == product_id).values(image_url=logo_key))
    await db_session.commit()
    published_image = await ac.get(
        f"/api/v1/storefront/products/{product_id}/image?preview_token={preview}"
    )
    assert published_image.status_code == 200, published_image.text
    catalog = await ac.get(
        f"/api/v1/storefront/bootstrap?preview_token={preview}&product_id={product_id}"
    )
    assert catalog.json()["data"]["catalog"][0]["image_url"] == f"/storefront/products/{product_id}/image"

    removed = await ac.delete("/api/v1/ecommerce/media/logo", headers=admin)
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["has_logo"] is False
    gone = await ac.get(f"/api/v1/storefront/media/logo?preview_token={preview}")
    assert gone.status_code == 404

    beta = await _login_beta(ac)
    leaked = await ac.get("/api/v1/ecommerce/media/banner", headers=beta)
    assert leaked.status_code == 403


def test_ecommerce_ui_and_docs_exist():
    page = (ROOT / "frontend/app/(dashboard)/ecommerce/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Storefront enabled"' in page
    assert 'aria-label="Custom domain hostname"' in page
    assert 'aria-label="Link company website"' in page
    assert "Unlink website" in page
    assert "Disconnect ${row.platform} website" in page
    assert 'aria-label="Retry failed connector jobs"' in page
    assert 'aria-label="Storefront status"' in page
    assert "There is no public Ribdigi subdomain" in page
    assert "Certificates stay an owner task" in page
    assert 'aria-label="Online catalog search"' in page
    assert "Storefront logo file" in page
    assert "Storefront banner file" in page
    assert "Storefront favicon file" in page
    assert "This is separate from the ERP sidebar logo" in page
    assert "No {kind} uploaded" in page
    assert "ecom-media" in page
    assert "Verify the hostname before recording HTTPS ready" in page
    assert "ecom-desk" in page
    assert "ecom-storefront" in page
    assert "ecom-domains" in page
    assert "ecom-catalog" in page
    assert "ecom-orders" in page
    assert "ecom-payments" in page
    assert "ecom-woo" in page
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    sales = shell[shell.find("id: 'sales'") : shell.find("id: 'purchases'")]
    settings = shell[shell.find("id: 'settings'") : shell.find("id: 'industry'")]
    assert "/ecommerce" not in sales
    assert "['Online store', '/ecommerce', 'ecommerce']" in settings
    storefront = (ROOT / "frontend/app/storefront/page.tsx").read_text(encoding="utf-8")
    chrome = (ROOT / "frontend/app/storefront/StorefrontShell.tsx").read_text(encoding="utf-8")
    cart = (ROOT / "frontend/app/storefront/cart/page.tsx").read_text(encoding="utf-8")
    product = (ROOT / "frontend/app/storefront/product/[id]/page.tsx").read_text(encoding="utf-8")
    assert "Add to cart" in storefront
    assert 'aria-label="Storefront search"' in storefront
    assert "sf-hero" in storefront
    assert "storefront/media/banner" in storefront
    assert "No products match this search" in storefront
    assert "/storefront/account" in chrome
    assert "This store is not available" in chrome
    assert "storefront/media/logo" in chrome
    assert "Remove ${line.name} from cart" in cart
    assert "product_id" in product
    checkout = (ROOT / "frontend/app/storefront/checkout/page.tsx").read_text(encoding="utf-8")
    assert "Guest checkout" in checkout
    assert 'aria-label="Checkout customer phone"' in checkout
    assert "Your cart is empty" in checkout
    assert "Could not load cart" in checkout
    assert "Could not load cart" in cart
    account = (ROOT / "frontend/app/storefront/account/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create storefront account"' in account
    docs = (ROOT / "docs/ECOMMERCE.md").read_text(encoding="utf-8")
    assert "verified hostname" in docs.lower()
    assert "WooCommerce" in docs
    api = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ecommerce" in api
    assert "expire_ecommerce_reservations" in api
    assert "product_id" in api
    assert "storefront media" in api.lower() or "/ecommerce/media" in api
    assert "has_logo" in docs.lower() or "logo" in docs.lower()
