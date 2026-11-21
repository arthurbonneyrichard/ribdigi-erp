"""FMCG promotions: approval, eligibility, budget and use limits, scope, performance."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"
PROMO = f"{API}/promotions"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _manager(ac, db_session, seed, email="manager@alpha.example.com", role="fmcg_manager", tenant="t1", slug="alpha"):
    db_session.add(m.User(
        tenant_id=seed[tenant].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
        role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug=slug)


async def _product(db_session, seed, price=100, cost=60, stock=500, category_id=None):
    row = m.Product(
        tenant_id=seed["t1"].id, name=f"Tin {uuid4().hex[:5]}", sku=f"P{uuid4().hex[:7]}", cost_price=cost,
        selling_price=price, stock_qty=stock, is_active=True, tracks_batches=False, category_id=category_id)
    db_session.add(row)
    await db_session.commit()
    return SimpleNamespace(id=row.id)


async def _outlet(ac, h, **extra):
    return (await ac.post(f"{API}/outlets", headers=h, json={"name": f"Kiosk {uuid4().hex[:5]}", **extra})).json()["data"]["id"]


async def _book(ac, h, outlet, product, qty=2):
    r = await ac.post(f"{API}/orders", headers=h, json={
        "customer_id": outlet, "terms": "credit", "lines": [{"product_id": product.id, "quantity": qty}]})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _body(product=None, **extra):
    body = {"code": f"P{uuid4().hex[:6]}", "name": "Promo", "scheme_type": "percent", "value": 10}
    if product:
        body["product_id"] = product.id
    body.update(extra)
    return body


@pytest.mark.asyncio
async def test_big_discount_needs_a_second_person(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    r = await ac.post(PROMO, headers=h, json=_body(p, value=50))
    assert r.status_code == 200, r.text
    promo = r.json()["data"]
    assert promo["status"] == "pending"
    # A pending promotion does not price anything.
    order = await _book(ac, h, await _outlet(ac, h), p)
    assert order["discount"] == 0
    r = await ac.post(f"{PROMO}/{promo['id']}/approve", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "SECOND_PERSON_NEEDED"
    mgr = await _manager(ac, db_session, seed)
    r = await ac.post(f"{PROMO}/{promo['id']}/approve", headers=mgr)
    assert r.status_code == 200 and r.json()["data"]["status"] == "approved"
    assert (await _book(ac, h, await _outlet(ac, h), p))["discount"] == 100
    assert (await ac.post(f"{PROMO}/{promo['id']}/approve", headers=mgr)).status_code == 409


@pytest.mark.asyncio
async def test_reject_needs_reason_and_policy_is_adjustable(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    promo = (await ac.post(PROMO, headers=h, json=_body(p, value=60))).json()["data"]
    mgr = await _manager(ac, db_session, seed)
    assert (await ac.post(f"{PROMO}/{promo['id']}/reject", headers=mgr, json={"reason": "!!"})).status_code == 422
    r = await ac.post(f"{PROMO}/{promo['id']}/reject", headers=mgr, json={"reason": "Margin too thin"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "rejected"
    assert (await _book(ac, h, await _outlet(ac, h), p))["discount"] == 0
    assert (await ac.put(f"{PROMO}/policy", headers=h, json={"approval_percent": 80, "approval_budget": 0})).status_code == 200
    assert (await ac.post(PROMO, headers=h, json=_body(p, value=60))).json()["data"]["status"] == "approved"
    assert (await ac.put(f"{PROMO}/policy", headers=h, json={"approval_percent": 101})).status_code == 422
    # A budget above the limit also needs approval.
    await ac.put(f"{PROMO}/policy", headers=h, json={"approval_percent": 100, "approval_budget": 1000})
    assert (await ac.post(PROMO, headers=h, json=_body(p, budget=5000))).json()["data"]["status"] == "pending"
    assert (await ac.post(PROMO, headers=h, json=_body(p, budget=500))).json()["data"]["status"] == "approved"


@pytest.mark.asyncio
async def test_budget_stops_the_promotion_and_cancelled_orders_give_it_back(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    promo = (await ac.post(PROMO, headers=h, json=_body(p, value=10, budget=25))).json()["data"]
    outlet = await _outlet(ac, h)
    first = await _book(ac, h, outlet, p, qty=2)   # 20 off, 5 left
    assert first["discount"] == 20
    assert (await _book(ac, h, outlet, p, qty=2))["discount"] == 0  # another 20 would pass the budget
    listed = [x for x in (await ac.get(PROMO, headers=h)).json()["data"] if x["id"] == promo["id"]][0]
    assert listed["spent"] == 20 and listed["budget_left"] == 5
    await ac.post(f"{API}/orders/{first['id']}/cancel", headers=h, json={"reason": "Outlet changed its mind"})
    assert (await _book(ac, h, outlet, p, qty=2))["discount"] == 20


@pytest.mark.asyncio
async def test_use_limit_min_qty_and_one_order_cannot_overspend(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    await ac.post(PROMO, headers=h, json=_body(p, value=10, max_uses=1, min_qty=3))
    outlet = await _outlet(ac, h)
    assert (await _book(ac, h, outlet, p, qty=2))["discount"] == 0  # under the minimum
    assert (await _book(ac, h, outlet, p, qty=3))["discount"] == 30
    assert (await _book(ac, h, outlet, p, qty=3))["discount"] == 0  # use limit reached
    q = await _product(db_session, seed)
    await ac.post(PROMO, headers=h, json=_body(q, value=10, budget=30))
    r = await ac.post(f"{API}/orders", headers=h, json={"customer_id": outlet, "terms": "credit", "lines": [
        {"product_id": q.id, "quantity": 2}, {"product_id": q.id, "quantity": 2}]})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["discount"] == 20  # second line would take it to 40, over the 30 budget


@pytest.mark.asyncio
async def test_targets_limit_a_promotion_to_outlet_route_or_territory(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    route = (await ac.post(f"{API}/routes", headers=h, json={"code": f"R{uuid4().hex[:5]}", "name": "North"})).json()["data"]
    on_route = await _outlet(ac, h, route_id=route["id"])
    elsewhere = await _outlet(ac, h)
    r = await ac.post(PROMO, headers=h, json=_body(p, targets=[{"kind": "route", "ref_id": route["id"]}]))
    assert r.status_code == 200, r.text
    assert (await _book(ac, h, on_route, p))["discount"] == 20
    assert (await _book(ac, h, elsewhere, p))["discount"] == 0
    # By outlet
    q = await _product(db_session, seed)
    await ac.post(PROMO, headers=h, json=_body(q, targets=[{"kind": "customer", "ref_id": elsewhere}]))
    assert (await _book(ac, h, elsewhere, q))["discount"] == 20
    assert (await _book(ac, h, on_route, q))["discount"] == 0
    # By territory
    terr = await ac.post(f"{API}/territories", headers=h, json={
        "code": f"T{uuid4().hex[:5]}", "name": "Zone", "route_ids": [route["id"]], "rep_user_ids": []})
    assert terr.status_code == 200, terr.text
    t = await _product(db_session, seed)
    await ac.post(PROMO, headers=h, json=_body(t, targets=[{"kind": "territory", "ref_id": terr.json()["data"]["id"]}]))
    assert (await _book(ac, h, on_route, t))["discount"] == 20
    assert (await _book(ac, h, elsewhere, t))["discount"] == 0
    bad = await ac.post(PROMO, headers=h, json=_body(p, targets=[{"kind": "route", "ref_id": str(uuid4())}]))
    assert bad.status_code == 404


@pytest.mark.asyncio
async def test_category_dates_and_best_single_scheme(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    cat = m.ProductCategory(tenant_id=seed["t1"].id, name="Drinks", code=f"C{uuid4().hex[:5]}")
    db_session.add(cat)
    await db_session.commit()
    p = await _product(db_session, seed, category_id=cat.id)
    other = await _product(db_session, seed)
    await ac.post(PROMO, headers=h, json=_body(category_id=cat.id, value=10))
    outlet = await _outlet(ac, h)
    assert (await _book(ac, h, outlet, p))["discount"] == 20
    assert (await _book(ac, h, outlet, other))["discount"] == 0
    # Schemes do not stack: the better one wins.
    await ac.post(PROMO, headers=h, json=_body(p, value=25))
    assert (await _book(ac, h, outlet, p))["discount"] == 50
    # Not started yet / already ended.
    future = await _product(db_session, seed)
    await ac.post(PROMO, headers=h, json=_body(future, starts_on=(date.today() + timedelta(days=5)).isoformat()))
    assert (await _book(ac, h, outlet, future))["discount"] == 0
    past = await _product(db_session, seed)
    await ac.post(PROMO, headers=h, json=_body(past, ends_on=(date.today() - timedelta(days=1)).isoformat()))
    assert (await _book(ac, h, outlet, past))["discount"] == 0


@pytest.mark.asyncio
async def test_performance_shows_cost_and_profit_after_delivery(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed, price=100, cost=60)
    promo = (await ac.post(PROMO, headers=h, json=_body(p, value=10, budget=500))).json()["data"]
    outlet = await _outlet(ac, h)
    order = await _book(ac, h, outlet, p, qty=5)
    perf = (await ac.get(f"{PROMO}/{promo['id']}/performance", headers=h)).json()["data"]
    assert perf["committed"]["discount"] == 50 and perf["delivered"]["lines"] == 0
    assert (await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})).status_code == 200
    perf = (await ac.get(f"{PROMO}/{promo['id']}/performance", headers=h)).json()["data"]
    d = perf["delivered"]
    assert d["units"] == 5 and d["discount_given"] == 50 and d["outlets"] == 1
    assert d["cost_of_goods"] == 300 and d["discount_per_unit"] == 10
    assert d["revenue_after_discount"] == d["gross_profit"] + 300
    assert perf["budget_used_pct"] == 10.0


@pytest.mark.asyncio
async def test_old_scheme_endpoint_follows_the_same_approval_rule(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    r = await ac.post(f"{API}/schemes", headers=h, json={
        "code": f"S{uuid4().hex[:5]}", "name": "Half price", "scheme_type": "percent", "value": 50, "product_id": p.id})
    assert r.status_code == 200 and r.json()["data"]["status"] == "pending"
    assert (await _book(ac, h, await _outlet(ac, h), p))["discount"] == 0


@pytest.mark.asyncio
async def test_promotions_roles_and_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed)
    promo = (await ac.post(PROMO, headers=h, json=_body(p, value=50))).json()["data"]
    rep = await _manager(ac, db_session, seed, email="rep@alpha.example.com", role="fmcg_rep")
    assert (await ac.get(PROMO, headers=rep)).status_code == 403
    assert (await ac.post(f"{PROMO}/{promo['id']}/approve", headers=rep)).status_code == 403
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    other = await _manager(ac, db_session, seed, email="admin@beta.example.com", role="company_admin", tenant="t2", slug="beta")
    assert (await ac.post(f"{PROMO}/{promo['id']}/approve", headers=other)).status_code == 404
    assert (await ac.post(f"{PROMO}/{promo['id']}/reject", headers=other, json={"reason": "Not yours"})).status_code == 404
    assert (await ac.get(f"{PROMO}/{promo['id']}/performance", headers=other)).status_code == 404
    assert (await ac.get(PROMO, headers=other)).json()["data"] == []
    r = await ac.post(PROMO, headers=other, json=_body(p))
    assert r.status_code == 404  # another company's product
