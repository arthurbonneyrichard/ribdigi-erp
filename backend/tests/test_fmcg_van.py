"""FMCG van sales: load, sell from the van, losses, costs, reconciliation and approval of differences."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _product(db_session, seed, stock=100, cost=6, price=10):
    row = m.Product(
        tenant_id=seed["t1"].id, name=f"Biscuit {uuid4().hex[:5]}", sku=f"V{uuid4().hex[:7]}",
        cost_price=cost, selling_price=price, stock_qty=stock, is_active=True, tracks_batches=False,
    )
    db_session.add(row)
    await db_session.commit()
    return SimpleNamespace(id=row.id)


async def _van(ac, h, product, qty=40):
    route = (await ac.post(f"{API}/routes", headers=h, json={"code": f"R{uuid4().hex[:5]}", "name": "Van"})).json()["data"]
    dispatch = (await ac.post(f"{API}/dispatches", headers=h, json={"route_id": route["id"]})).json()["data"]
    r = await ac.post(f"{API}/dispatches/{dispatch['id']}/van/load", headers=h,
                      json={"lines": [{"product_id": product.id, "quantity": qty}]})
    assert r.status_code == 200, r.text
    return dispatch["id"]


async def _outlet(ac, h):
    return (await ac.post(f"{API}/outlets", headers=h, json={"name": f"Kiosk {uuid4().hex[:5]}"})).json()["data"]["id"]


async def _sell(ac, h, dispatch, product, qty, terms="cash", method="cash"):
    outlet = await _outlet(ac, h)
    body = {"customer_id": outlet, "terms": terms, "lines": [{"product_id": product.id, "quantity": qty}]}
    if terms == "cash":
        body["payment_method"] = method
    return await ac.post(f"{API}/dispatches/{dispatch}/van/sales", headers=h, json=body)


async def _balanced(ac, h):
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)


@pytest.mark.asyncio
async def test_load_reserves_stock_and_blocks_over_loading(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed, stock=50)
    dispatch = await _van(ac, h, p, 40)
    route = (await ac.post(f"{API}/routes", headers=h, json={"code": f"R{uuid4().hex[:5]}", "name": "Second"})).json()["data"]
    other = (await ac.post(f"{API}/dispatches", headers=h, json={"route_id": route["id"]})).json()["data"]
    r = await ac.post(f"{API}/dispatches/{other['id']}/van/load", headers=h,
                      json={"lines": [{"product_id": p.id, "quantity": 20}]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "INSUFFICIENT_STOCK"
    assert (await ac.get(f"{API}/dispatches/{dispatch}/van", headers=h)).json()["data"]["lines"][0]["expected_back"] == 40


@pytest.mark.asyncio
async def test_van_sale_cash_credit_limits_and_stock(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    dispatch = await _van(ac, h, p, 40)
    r = await _sell(ac, h, dispatch, p, 15, "cash", "cash")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["order"]["status"] == "delivered"
    van = r.json()["data"]["van"]
    assert van["lines"][0]["sold"] == 15 and van["lines"][0]["expected_back"] == 25
    assert van["money"]["cash_collected"] == 150 and van["money"]["cash_to_hand_in"] == 150
    r = await _sell(ac, h, dispatch, p, 10, "credit")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["van"]["money"]["credit_sales"] == 100
    r = await _sell(ac, h, dispatch, p, 30, "credit")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NOT_ON_VAN"
    r = await _sell(ac, h, dispatch, p, 1, "cash", None)
    assert r.status_code == 422
    db_session.expire_all()
    assert float((await db_session.get(m.Product, p.id)).stock_qty) == 75
    await _balanced(ac, h)


@pytest.mark.asyncio
async def test_warehouse_delivery_cannot_eat_van_stock(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed, stock=50)
    await _van(ac, h, p, 40)
    outlet = await _outlet(ac, h)
    order = (await ac.post(f"{API}/orders", headers=h, json={
        "customer_id": outlet, "terms": "credit", "lines": [{"product_id": p.id, "quantity": 20}]})).json()["data"]
    r = await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_losses_and_expenses_reduce_van_and_cash(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    dispatch = await _van(ac, h, p, 40)
    await _sell(ac, h, dispatch, p, 10, "cash", "cash")
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/losses", headers=h,
                      json={"product_id": p.id, "quantity": 3, "kind": "damaged", "note": "Fell off the truck"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["cost"] == 18.0
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/losses", headers=h,
                      json={"product_id": p.id, "quantity": 2, "kind": "sample", "note": "Shop trial pack"})
    assert r.status_code == 200
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/losses", headers=h,
                      json={"product_id": p.id, "quantity": 99, "kind": "damaged", "note": "Too many"})
    assert r.status_code == 409
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/expenses", headers=h,
                      json={"kind": "fuel", "amount": 30, "note": "Diesel"})
    assert r.status_code == 200, r.text
    van = r.json()["data"]
    assert van["lines"][0]["expected_back"] == 25
    assert van["money"]["cash_to_hand_in"] == 70
    await _balanced(ac, h)


@pytest.mark.asyncio
async def test_clean_close_has_no_difference(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    dispatch = await _van(ac, h, p, 40)
    await _sell(ac, h, dispatch, p, 10, "cash", "cash")
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/close", headers=h,
                      json={"counted": [{"product_id": p.id, "quantity": 30}], "counted_cash": 100})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "closed" and data["cash_variance"] == 0 and data["stock_variance_value"] == 0
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/close", headers=h,
                      json={"counted": [{"product_id": p.id, "quantity": 30}], "counted_cash": 100})
    assert r.status_code == 409
    db_session.expire_all()
    assert float((await db_session.get(m.Product, p.id)).stock_qty) == 90


@pytest.mark.asyncio
async def test_variance_needs_manager_and_reason_and_is_posted(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    dispatch = await _van(ac, h, p, 40)
    await _sell(ac, h, dispatch, p, 10, "cash", "cash")
    body = {"counted": [{"product_id": p.id, "quantity": 27}], "counted_cash": 95}
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/close", headers=h, json=body)
    assert r.status_code == 400  # a difference needs a written reason
    # A driver cannot close a van that has a difference.
    db_session.add(m.User(
        tenant_id=seed["t1"].id, email="driver@alpha.example.com", full_name="Van Driver",
        password_hash=hash_password("SecurePass123!"), role="fmcg_driver", email_verified=True,
        permissions=permissions_for_role("fmcg_driver"), totp_enabled=False))
    await db_session.commit()
    d = await auth_headers(ac, email="driver@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/close", headers=d, json={**body, "note": "Short by three"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "VAN_VARIANCE_NEEDS_MANAGER"
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/close", headers=h, json={**body, "note": "Three packs went missing"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["stock_variance_value"] == -18.0 and data["cash_variance"] == -5.0
    db_session.expire_all()
    assert float((await db_session.get(m.Product, p.id)).stock_qty) == 87
    await _balanced(ac, h)
    perf = (await ac.get(f"{API}/van/performance", headers=h)).json()["data"]
    assert perf[0]["cash_variance"] == -5.0 and perf[0]["sales"] == 100


@pytest.mark.asyncio
async def test_must_count_every_product_and_driver_can_sell(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    dispatch = await _van(ac, h, p, 40)
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/close", headers=h, json={"counted": [], "counted_cash": 0})
    assert r.status_code == 422
    db_session.add(m.User(
        tenant_id=seed["t1"].id, email="rep@alpha.example.com", full_name="Van Rep",
        password_hash=hash_password("SecurePass123!"), role="fmcg_rep", email_verified=True,
        permissions=permissions_for_role("fmcg_rep"), totp_enabled=False))
    await db_session.commit()
    rep = await auth_headers(ac, email="rep@alpha.example.com", tenant_slug="alpha")
    r = await _sell(ac, rep, dispatch, p, 5, "cash", "cash")
    assert r.status_code == 200, r.text
    assert (await ac.get(f"{API}/van/performance", headers=rep)).status_code == 403


@pytest.mark.asyncio
async def test_van_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    dispatch = await _van(ac, h, p, 10)
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    db_session.add(m.User(
        tenant_id=seed["t2"].id, email="admin@beta.example.com", full_name="Beta Admin",
        password_hash=hash_password("SecurePass123!"), role="company_admin", email_verified=True,
        permissions=permissions_for_role("company_admin"), totp_enabled=False))
    await db_session.commit()
    other = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    assert (await ac.get(f"{API}/dispatches/{dispatch}/van", headers=other)).status_code == 404
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/expenses", headers=other, json={"kind": "fuel", "amount": 5})
    assert r.status_code == 404
    r = await ac.post(f"{API}/dispatches/{dispatch}/van/close", headers=other, json={"counted": [], "counted_cash": 0})
    assert r.status_code == 404
