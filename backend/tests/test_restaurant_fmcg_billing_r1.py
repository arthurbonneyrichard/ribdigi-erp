"""Restaurant floor, FMCG pack/expiry, and platform billing gateway setup."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app.billing_gateway import MockGateway
from app.config import settings
from app.jobs import job_process_subscription_renewals
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, platform_owner_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_mock_charges():
    MockGateway._charged.clear()
    yield
    MockGateway._charged.clear()


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _product(ac, headers, **extra):
    body = {"name": extra.pop("name"), "selling_price": extra.pop("selling_price", 10), **extra}
    created = await ac.post("/api/v1/products", json=body, headers=headers)
    assert created.status_code == 200, created.text
    return created.json()["data"]


async def test_retail_and_hotel_cannot_use_restaurant_routes(client, db_session):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert denied.status_code == 403, denied.text
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    still = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert still.status_code == 403, still.text
    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert rooms.status_code == 200, rooms.text


async def test_restaurant_order_kitchen_and_ingredient_deduction(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    ingredient = await _product(ac, admin, name="Rice", selling_price=1, stock_qty=10)
    dish = await _product(ac, admin, name="Jollof", selling_price=20, prep_station="kitchen")
    group = await ac.post("/api/v1/restaurant/modifier-groups", json={"name": "Extras"}, headers=admin)
    assert group.status_code == 200, group.text
    modifier = await ac.post(
        f"/api/v1/restaurant/modifier-groups/{group.json()['data']['id']}/modifiers",
        json={"name": "Cheese", "price": "2"},
        headers=admin,
    )
    assert modifier.status_code == 200, modifier.text
    recipe = await ac.post(
        "/api/v1/restaurant/recipes",
        json={
            "product_id": dish["id"],
            "name": "Jollof recipe",
            "lines": [{"ingredient_id": ingredient["id"], "quantity": "2"}],
        },
        headers=admin,
    )
    assert recipe.status_code == 200, recipe.text
    table = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "T1", "name": "Window"},
        headers=admin,
    )
    assert table.status_code == 200, table.text
    order = await ac.post(
        "/api/v1/restaurant/orders",
        json={
            "service_mode": "dine_in",
            "payment_method": "cash",
            "table_id": table.json()["data"]["id"],
            "lines": [
                {
                    "product_id": dish["id"],
                    "quantity": "1",
                    "modifier_ids": [modifier.json()["data"]["id"]],
                }
            ],
        },
        headers=admin,
    )
    assert order.status_code == 200, order.text
    body = order.json()["data"]
    assert body["total_amount"] == 22
    order_id = body["id"]
    sent = await ac.post(f"/api/v1/restaurant/orders/{order_id}/send", headers=admin)
    assert sent.status_code == 200, sent.text
    kitchen = await ac.get("/api/v1/restaurant/kitchen", headers=admin)
    assert kitchen.status_code == 200, kitchen.text
    assert any(row["station"] == "kitchen" for row in kitchen.json()["data"])
    done = await ac.post(f"/api/v1/restaurant/orders/{order_id}/complete", headers=admin)
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "completed"
    stock = await ac.get(f"/api/v1/products/{ingredient['id']}", headers=admin)
    assert stock.status_code == 200, stock.text
    assert float(stock.json()["data"]["stock_qty"]) == 8
    summary = await ac.get("/api/v1/restaurant/summary", headers=admin)
    assert summary.json()["data"]["sales_today"] == 22
    reports = await ac.get("/api/v1/restaurant/reports", headers=admin)
    modes = {row["service_mode"] for row in reports.json()["data"]["by_service_mode"]}
    assert "dine_in" in modes
    beta = m.User(
        tenant_id=seed["t2"].id,
        email="admin@beta.example.com",
        full_name="Beta Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
    )
    db_session.add(beta)
    await db_session.commit()
    await set_tenant_industry(db_session, seed["t2"], "restaurant")
    other = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    leaked = await ac.post(f"/api/v1/restaurant/orders/{order_id}/refund", headers=other)
    assert leaked.status_code == 404, leaked.text


async def test_store_scoped_user_cannot_see_another_store_table(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    store_a = await ac.post("/api/v1/stores", json={"name": "Kitchen A", "code": "KA"}, headers=admin)
    store_b = await ac.post("/api/v1/stores", json={"name": "Kitchen B", "code": "KB"}, headers=admin)
    assert store_a.status_code == 200, store_a.text
    assert store_b.status_code == 200, store_b.text
    table = await ac.post(
        "/api/v1/restaurant/tables",
        json={"code": "A1", "name": "Store A", "store_id": store_a.json()["data"]["id"]},
        headers=admin,
    )
    assert table.status_code == 200, table.text
    cashier = (
        await db_session.execute(select(m.User).where(m.User.email == "cashier@alpha.example.com"))
    ).scalar_one()
    db_session.add(
        m.UserStoreMembership(
            tenant_id=seed["t1"].id,
            user_id=cashier.id,
            store_id=store_b.json()["data"]["id"],
            is_active=True,
        )
    )
    await db_session.commit()
    scoped = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    listed = await ac.get("/api/v1/restaurant/tables", headers=scoped)
    assert listed.status_code == 200, listed.text
    assert all(row["code"] != "A1" for row in listed.json()["data"])


async def test_fmcg_pack_conversion_and_expired_lot_block(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    piece = await ac.post("/api/v1/catalog/units", json={"name": "Piece", "code": "PCXF"}, headers=admin)
    assert piece.status_code == 200, piece.text
    carton = await ac.post(
        "/api/v1/catalog/units",
        json={
            "name": "Carton",
            "code": "CTNF",
            "base_unit_id": piece.json()["data"]["id"],
            "conversion_ratio": 12,
        },
        headers=admin,
    )
    assert carton.status_code == 200, carton.text
    product = await _product(
        ac,
        admin,
        name="Soap",
        selling_price=5,
        stock_qty=0,
        tracks_batches=True,
        unit_id=piece.json()["data"]["id"],
    )
    converted = await ac.post(
        "/api/v1/fmcg/pack-convert",
        json={"product_id": product["id"], "from_unit_id": carton.json()["data"]["id"], "quantity": 2},
        headers=admin,
    )
    assert converted.status_code == 403, converted.text
    assert converted.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"
    db_session.add(
        m.ProductBatch(
            tenant_id=seed["t1"].id,
            product_id=product["id"],
            batch_number="OLD",
            expiry_date=datetime.utcnow() - timedelta(days=2),
            quantity=5,
        )
    )
    await db_session.commit()
    blocked = await ac.post(
        "/api/v1/inventory/stock-out",
        json={"product_id": product["id"], "quantity": 1, "reference_type": "sale"},
        headers=admin,
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "NO_SALEABLE_BATCH"
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    hotel = await ac.post(
        "/api/v1/fmcg/pack-convert",
        json={"product_id": product["id"], "from_unit_id": carton.json()["data"]["id"], "quantity": 1},
        headers=admin,
    )
    assert hotel.status_code == 403, hotel.text
    assert hotel.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"


async def _save_mock(ac, owner):
    saved = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "mock", "mode": "sandbox", "secret": "mocksecret1", "webhook_secret": "webhooksec1"},
        headers=owner,
    )
    assert saved.status_code == 200, saved.text
    assert "mocksecret1" not in saved.text
    assert saved.json()["data"]["connected"] is False
    return saved.json()["data"]


async def test_gateway_rejects_invalid_credentials_and_ssrf(client, db_session):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    bad = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "mock", "mode": "sandbox", "secret": "!!!"},
        headers=owner,
    )
    assert bad.status_code == 422, bad.text
    paystack = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "paystack", "mode": "sandbox", "secret": "not_a_test_key"},
        headers=owner,
    )
    assert paystack.status_code == 422, paystack.text
    ssrf = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={
            "provider": "paystack",
            "mode": "sandbox",
            "api_base_url": "http://127.0.0.1/charge",
            "secret": "sk_test_abcdefgh",
        },
        headers=owner,
    )
    assert ssrf.status_code == 422, ssrf.text
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    forbidden = await ac.put(
        "/api/v1/platform/billing/gateway",
        json={"provider": "mock", "mode": "sandbox", "secret": "mocksecret1"},
        headers=admin,
    )
    assert forbidden.status_code == 403, forbidden.text


async def test_connection_test_does_not_charge(client, db_session):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    await _save_mock(ac, owner)
    early = await ac.post("/api/v1/platform/billing/gateway/enable", headers=owner)
    assert early.status_code == 422, early.text
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    tested_body = tested.json()["data"]
    assert tested_body["last_test_ok"] is True
    assert tested_body["last_test_at"]
    assert tested_body["last_test_message"] == "sandbox_ready"
    assert tested_body["enabled"] is False
    assert tested_body["connected"] is False
    assert tested_body["secret_configured"] is True
    assert "mocksecret1" not in tested.text
    assert "secret" not in tested_body
    assert "webhook_secret" not in tested_body
    assert MockGateway._charged == set()
    enabled = await ac.post("/api/v1/platform/billing/gateway/enable", headers=owner)
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["data"]["connected"] is True
    rotated = await ac.post(
        "/api/v1/platform/billing/gateway/rotate",
        json={"secret": "mocksecret2"},
        headers=owner,
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["data"]["enabled"] is False
    assert rotated.json()["data"]["connected"] is False
    assert "mocksecret2" not in rotated.text


async def test_failed_connection_keeps_saved_gateway(client, db_session, monkeypatch):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    await _save_mock(ac, owner)
    monkeypatch.setattr(MockGateway, "test_connection", lambda self: (False, "sandbox_refused"))
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    tested_body = tested.json()["data"]
    assert tested_body["last_test_ok"] is False
    assert tested_body["last_test_message"] == "sandbox_refused"
    assert tested_body["last_test_at"]
    assert tested_body["enabled"] is False
    assert tested_body["secret_configured"] is True
    assert "mocksecret1" not in tested.text
    assert "secret" not in tested_body
    assert MockGateway._charged == set()
    status = await ac.get("/api/v1/platform/billing/status", headers=owner)
    assert status.status_code == 200, status.text
    payload = status.json()["data"]
    assert payload["configured"] is True
    assert payload["live_charges"] is False
    assert payload["gateway"]["secret_configured"] is True
    assert payload["gateway"]["last_test_ok"] is False
    assert payload["gateway"]["enabled"] is False
    assert "mocksecret1" not in status.text


async def _enable_mock(ac, owner):
    await _save_mock(ac, owner)
    tested = await ac.post("/api/v1/platform/billing/gateway/test", headers=owner)
    assert tested.status_code == 200, tested.text
    enabled = await ac.post("/api/v1/platform/billing/gateway/enable", headers=owner)
    assert enabled.status_code == 200, enabled.text


async def test_failed_renewal_does_not_capture(client, db_session):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    await _enable_mock(ac, owner)
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "professional-month", "next_renewal_at": past},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    consent = await ac.post(
        "/api/v1/billing/consent",
        json={"plan_code": "professional-month", "accept": True},
        headers=admin,
    )
    assert consent.status_code == 200, consent.text
    saved = await ac.post(
        "/api/v1/billing/sandbox/authorize",
        json={"authorization_code": "mock_auth_fail_card"},
        headers=admin,
    )
    assert saved.status_code == 200, saved.text
    failed = await job_process_subscription_renewals()
    assert failed["failed"] == 1
    assert failed["charged"] == 0
    assert MockGateway._charged == set()


async def test_successful_renewal_webhook_and_currencies(client, db_session):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    await _enable_mock(ac, owner)
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "professional-month", "next_renewal_at": past},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    consent = await ac.post(
        "/api/v1/billing/consent",
        json={"plan_code": "professional-month", "accept": True},
        headers=admin,
    )
    assert consent.status_code == 200, consent.text
    saved_ok = await ac.post(
        "/api/v1/billing/sandbox/authorize",
        json={"authorization_code": "mock_auth_ok_safe1"},
        headers=admin,
    )
    assert saved_ok.status_code == 200, saved_ok.text
    charged = await job_process_subscription_renewals()
    assert charged["charged"] == 1
    invoices = (await ac.get("/api/v1/billing/invoices", headers=admin)).json()["data"]
    assert invoices
    event = {
        "id": "evt-gateway-1",
        "event": "charge.success",
        "data": {
            "reference": invoices[0]["idempotency_key"],
            "amount": 49900,
            "currency": "GHS",
            "tenant_id": seed["t1"].id,
            "gateway_reference": "mock_tx_gateway",
        },
    }
    raw = json.dumps(event, separators=(",", ":")).encode()
    bad_sig = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw,
        headers={"x-ribdigi-billing-signature": "deadbeef", "content-type": "application/json"},
    )
    assert bad_sig.status_code == 401, bad_sig.text
    signature = _sign(raw, "webhooksec1")
    first = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw,
        headers={"x-ribdigi-billing-signature": signature, "content-type": "application/json"},
    )
    second = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw,
        headers={"x-ribdigi-billing-signature": signature, "content-type": "application/json"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["duplicate"] is False
    assert second.json()["data"]["duplicate"] is True
    ghs = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "ghs-month",
            "name": "GHS month",
            "package_code": "professional",
            "interval": "month",
            "amount": "499.00",
            "currency": "GHS",
            "trial_days": 14,
            "grace_days": 7,
        },
        headers=owner,
    )
    assert ghs.status_code == 200, ghs.text
    usd = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "usd-month",
            "name": "USD month",
            "package_code": "professional",
            "interval": "month",
            "amount": "49.00",
            "currency": "USD",
            "trial_days": 0,
            "grace_days": 7,
        },
        headers=owner,
    )
    assert usd.status_code == 200, usd.text
    euro = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "eur-month",
            "name": "EUR month",
            "package_code": "professional",
            "interval": "month",
            "amount": "49.00",
            "currency": "EUR",
            "trial_days": 0,
            "grace_days": 7,
        },
        headers=owner,
    )
    assert euro.status_code == 422, euro.text
    assert settings.BILLING_PROVIDER


async def test_migration_skips_tables_that_already_exist():
    import importlib.util
    from pathlib import Path

    from sqlalchemy import create_engine, inspect

    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext

    engine = create_engine("sqlite://")
    m.Base.metadata.create_all(engine)
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261008_0135_restaurant_and_billing_gateway.py"
    spec = importlib.util.spec_from_file_location("restaurant_billing_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "20261008_0117"
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            module.upgrade()
            module.upgrade()
        names = set(inspect(conn).get_table_names())
    assert "platform_billing_gateways" in names
    assert "restaurant_orders" in names
    assert "restaurant_tables" in names
