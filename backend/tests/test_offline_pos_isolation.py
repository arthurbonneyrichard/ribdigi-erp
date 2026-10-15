"""Isolation, idempotent sync, price/stock conflict, and expired offline POS."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app.offline_pos import (
    DEFAULT_OFFLINE_AUTH_HOURS,
    OFFLINE_COMPLETE_MISSING,
    clamp_offline_auth_hours,
    offline_window_expired,
)
from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _beta_cashier(ac):
    return await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")


@pytest.mark.asyncio
async def test_tenant_a_cannot_read_search_or_export_tenant_b(client):
    ac, seed = client
    headers = await _cashier(ac)
    r = await ac.get("/api/v1/products", headers=headers)
    assert r.status_code == 200
    names = {p["name"] for p in r.json()["data"]}
    assert "Beta Widget" not in names

    search = await ac.get("/api/v1/pos/products/search", headers=headers, params={"q": "Beta"})
    assert search.status_code == 200
    found = {row.get("name") for row in search.json()["data"]}
    assert "Beta Widget" not in found

    foreign = await ac.get(f"/api/v1/products/{seed['p2'].id}", headers=headers)
    assert foreign.status_code == 404

    hijack = await ac.patch(
        f"/api/v1/products/{seed['p2'].id}",
        headers=headers,
        json={"name": "Hijacked"},
    )
    assert hijack.status_code in {403, 404, 405, 422}

    stolen_store = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 0, "store_id": seed["p2"].id},
    )
    assert stolen_store.status_code in {400, 403, 404, 422}

    admin = await _admin(ac, seed)
    export = await ac.get(
        "/api/v1/reports/export",
        headers=admin,
        params={"report_type": "sales_daily", "format": "csv", "store_id": seed["p2"].id},
    )
    assert export.status_code in {400, 403, 404, 422}

    await ac.post(
        "/api/v1/pos/devices/heartbeat",
        headers=headers,
        json={"device_id": "dev-alpha-isolation01", "pending_queue_count": 0},
    )
    beta = await _beta_cashier(ac)
    listed = await ac.get("/api/v1/pos/devices", headers=beta)
    assert listed.status_code == 200
    ids = {d.get("device_id") for d in listed.json()["data"] or []}
    assert "dev-alpha-isolation01" not in ids


@pytest.mark.asyncio
async def test_store_assignment_does_not_grant_extra_rbac(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    cashier = await _cashier(ac)
    created = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "ISO1", "name": "Isolation Store"},
    )
    assert created.status_code == 200, created.text
    store_id = created.json()["data"]["id"]
    assigned = await ac.put(
        f"/api/v1/users/{seed['u1'].id}/stores",
        headers=admin,
        json={"store_ids": [store_id]},
    )
    assert assigned.status_code == 200, assigned.text
    denied_users = await ac.get("/api/v1/users", headers=cashier)
    assert denied_users.status_code == 403
    denied_create = await ac.post(
        "/api/v1/users",
        headers=cashier,
        json={
            "email": "nobody@alpha.example.com",
            "full_name": "Nobody",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert denied_create.status_code == 403


@pytest.mark.asyncio
async def test_session_store_used_when_cashier_has_one_assignment(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    cashier = await _cashier(ac)
    created = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "ONEA", "name": "Only Store"},
    )
    assert created.status_code == 200, created.text
    store_id = created.json()["data"]["id"]
    await ac.put(
        f"/api/v1/users/{seed['u1'].id}/stores",
        headers=admin,
        json={"store_ids": [store_id]},
    )
    cur = await ac.get("/api/v1/pos/sessions/current", headers=cashier)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            await ac.post(f"/api/v1/pos/sessions/{sid}/close", headers=admin, json={"actual_cash": 0})
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 0},
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["data"]["store_id"] == store_id


@pytest.mark.asyncio
async def test_offline_policy_default_is_168_hours(client):
    ac, _seed = client
    headers = await _cashier(ac)
    r = await ac.get("/api/v1/pos/offline-policy", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["offline_auth_hours_default"] == DEFAULT_OFFLINE_AUTH_HOURS
    assert data["offline_auth_hours"] == 168
    assert data["offline_complete_claimed"] is False
    assert "max_sync_retries" not in data
    assert OFFLINE_COMPLETE_MISSING in data["limitations"]
    assert "inventory" in data["not_offline"]
    assert clamp_offline_auth_hours(999) == 168
    assert clamp_offline_auth_hours(0) == 1


async def _open_shift(ac, headers, admin=None):
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if cur.status_code == 200 and cur.json().get("data"):
        sid = cur.json()["data"].get("session_id") or cur.json()["data"].get("id")
        if sid:
            closer = admin or headers
            await ac.post(
                f"/api/v1/pos/sessions/{sid}/close",
                headers=closer,
                json={"actual_cash": 0},
            )
    opened = await ac.post("/api/v1/pos/sessions/open", headers=headers, json={"opening_cash": 0})
    assert opened.status_code == 200, opened.text
    return opened.json()["data"].get("session_id") or opened.json()["data"]["id"]


@pytest.mark.asyncio
async def test_offline_sync_price_conflict_does_not_drop_or_create_sale(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 20
    product.selling_price = 10
    await db_session.commit()
    admin = await _admin(ac, seed)
    session_id = await _open_shift(ac, headers, admin)
    body = {
        "session_id": session_id,
        "client_request_id": "cr-conflict-price-001",
        "offline_sync": True,
        "offline_created_at": datetime.utcnow().isoformat(),
        "device_id": "dev-test01",
        "payment_method": "cash",
        "status": "completed",
        "items": [{"product_id": product.id, "quantity": 1, "unit_price": 99}],
    }
    conflicted = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert conflicted.status_code == 409, conflicted.text
    assert conflicted.json()["detail"]["code"] == "PRICE_CONFLICT"

    listed = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    assert listed.status_code == 200

    replay = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert replay.status_code == 409

    body["items"][0]["unit_price"] = 10
    ok = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert ok.status_code == 200, ok.text
    sale_id = ok.json()["data"]["id"]
    again = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert again.status_code == 200
    assert again.json()["data"]["id"] == sale_id
    assert again.json()["data"].get("idempotent_replay") is True


@pytest.mark.asyncio
async def test_offline_sync_stock_conflict_visible(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    product = seed["p1"]
    product.stock_qty = 0
    product.selling_price = 10
    await db_session.commit()
    admin = await _admin(ac, seed)
    session_id = await _open_shift(ac, headers, admin)
    body = {
        "session_id": session_id,
        "client_request_id": "cr-conflict-stock-001",
        "offline_sync": True,
        "offline_created_at": datetime.utcnow().isoformat(),
        "device_id": "dev-test02",
        "payment_method": "cash",
        "status": "completed",
        "items": [{"product_id": product.id, "quantity": 5, "unit_price": 10}],
    }
    r = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] in {"STOCK_CONFLICT", "INSUFFICIENT_WAREHOUSE_STOCK"}


@pytest.mark.asyncio
async def test_old_legacy_queued_sale_syncs_for_online_user(client, db_session):
    """A sale queued before server grants existed syncs once the user is online-authenticated.

    The device's offline window lapsing must not strand sales recorded while it was valid.
    """
    ac, seed = client
    headers = await _cashier(ac)
    product = seed["p1"]
    product.stock_qty = float(product.stock_qty or 0) + 5
    product.selling_price = 10
    await db_session.commit()
    admin = await _admin(ac, seed)
    session_id = await _open_shift(ac, headers, admin)
    stale = (datetime.utcnow() - timedelta(days=10)).isoformat()
    assert offline_window_expired(
        offline_created_at=datetime.utcnow() - timedelta(days=10),
        hours=168,
    )
    body = {
        "session_id": session_id,
        "client_request_id": "cr-expired-offline-001",
        "offline_sync": True,
        "offline_created_at": stale,
        "device_id": "dev-test03",
        "payment_method": "cash",
        "status": "completed",
        "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
    }
    r = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert r.status_code == 200, r.text
    replay = await ac.post("/api/v1/pos/sales", headers=headers, json=body)
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == r.json()["data"]["id"]
    assert replay.json()["data"]["idempotent_replay"] is True


@pytest.mark.asyncio
async def test_beta_cannot_sync_alpha_client_request_id(client):
    ac, seed = client
    alpha = await _cashier(ac)
    product = seed["p1"]
    session_id = await _open_shift(ac, alpha, await _admin(ac, seed))
    body = {
        "session_id": session_id,
        "client_request_id": "cr-cross-tenant-001",
        "payment_method": "cash",
        "status": "completed",
        "items": [{"product_id": product.id, "quantity": 1, "unit_price": 10}],
    }
    first = await ac.post("/api/v1/pos/sales", headers=alpha, json=body)
    assert first.status_code == 200, first.text
    alpha_id = first.json()["data"]["id"]

    beta = await _beta_cashier(ac)
    stolen = await ac.get(f"/api/v1/pos/sales/{alpha_id}/receipt", headers=beta)
    assert stolen.status_code in {403, 404}
