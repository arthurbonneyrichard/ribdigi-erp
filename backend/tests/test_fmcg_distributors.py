"""FMCG distributors: terms, price tier, statements, performance and flags."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"
D = f"{API}/distributors"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _user(ac, db_session, seed, email, role, tenant="t1", slug="alpha"):
    db_session.add(m.User(tenant_id=seed[tenant].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
                          role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug=slug)


async def _product(db_session, seed, price=100, cost=60, stock=5000):
    p = m.Product(tenant_id=seed["t1"].id, name=f"Flour {uuid4().hex[:4]}", sku=f"D{uuid4().hex[:7]}", cost_price=cost, selling_price=price,
                  stock_qty=stock, is_active=True, tracks_batches=False)
    db_session.add(p)
    await db_session.commit()
    return p.id


async def _outlet(ac, h, **extra):
    return (await ac.post(f"{API}/outlets", headers=h, json={"name": f"Wholesale {uuid4().hex[:4]}", **extra})).json()["data"]["id"]


async def _deliver(ac, h, outlet, pid, qty, terms="credit"):
    order = (await ac.post(f"{API}/orders", headers=h, json={"customer_id": outlet, "terms": terms, "lines": [{"product_id": pid, "quantity": qty}]})).json()["data"]
    r = await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})
    assert r.status_code == 200, r.text
    return order


@pytest.mark.asyncio
async def test_profile_rules_and_listing(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    o = await _outlet(ac, h)
    r = await ac.post(D, headers=h, json={"customer_id": o, "kind": "wholesaler", "price_discount_pct": 8, "monthly_target": 5000})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["kind"] == "wholesaler" and d["price_discount_pct"] == 8 and d["target_pct"] == 0 and d["sales_this_month"] == 0
    assert (await ac.post(D, headers=h, json={"customer_id": o})).status_code == 409
    assert (await ac.post(D, headers=h, json={"customer_id": str(uuid4())})).status_code == 404
    assert (await ac.post(D, headers=h, json={"customer_id": await _outlet(ac, h), "price_discount_pct": 80})).status_code == 422
    assert (await ac.post(D, headers=h, json={"customer_id": await _outlet(ac, h), "territory_id": str(uuid4())})).status_code == 404
    r = await ac.patch(f"{D}/{d['id']}", headers=h, json={"price_discount_pct": 10, "kind": "key_account"})
    assert r.json()["data"]["price_discount_pct"] == 10 and r.json()["data"]["kind"] == "key_account"
    assert (await ac.patch(f"{D}/{d['id']}", headers=h, json={"kind": "friend"})).status_code == 422
    assert len((await ac.get(D, headers=h)).json()["data"]) == 1


@pytest.mark.asyncio
async def test_price_tier_applies_before_promotions(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid = await _product(db_session, seed, price=100)
    dist, plain = await _outlet(ac, h), await _outlet(ac, h)
    prof = (await ac.post(D, headers=h, json={"customer_id": dist, "price_discount_pct": 10})).json()["data"]
    mk = lambda c: ac.post(f"{API}/orders", headers=h, json={"customer_id": c, "terms": "credit", "lines": [{"product_id": pid, "quantity": 10}]})
    tier, normal = (await mk(dist)).json()["data"], (await mk(plain)).json()["data"]
    assert tier["lines"][0]["unit_price"] == 90 and normal["lines"][0]["unit_price"] == 100
    assert tier["subtotal"] < normal["subtotal"] and tier["discount"] == 0
    await ac.post(f"{API}/promotions", headers=h, json={"code": "TEN", "name": "Ten off", "scheme_type": "percent", "value": 10, "product_id": pid})
    both = (await mk(dist)).json()["data"]
    assert both["lines"][0]["unit_price"] == 90 and both["discount"] == 90  # 10% of the tier price, not of the list price
    await ac.patch(f"{D}/{prof['id']}", headers=h, json={"is_active": False})
    assert (await mk(dist)).json()["data"]["lines"][0]["unit_price"] == 100  # a switched-off profile gives no tier


@pytest.mark.asyncio
async def test_statement_balances_work_back_correctly(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid = await _product(db_session, seed, price=100)
    o = await _outlet(ac, h)
    d = (await ac.post(D, headers=h, json={"customer_id": o})).json()["data"]
    first = await _deliver(ac, h, o, pid, 10)
    pay = await ac.post(f"{API}/collections", headers=h, json={"customer_id": o, "amount": 300, "method": "cash"})
    assert pay.status_code == 200, pay.text
    await _deliver(ac, h, o, pid, 5)
    st = (await ac.get(f"{D}/{d['id']}/statement", headers=h)).json()["data"]
    total = st["total_debits"]
    assert st["opening_balance"] == 0 and len(st["lines"]) == 3
    assert [l["kind"].split(" ")[0] for l in st["lines"]].count("Delivery") == 2
    assert st["closing_balance"] == round(total - 300, 2) == st["lines"][-1]["balance"]
    assert st["total_credits"] == 300
    # A period that ended yesterday still reconciles to today's balance.
    old = (await ac.get(f"{D}/{d['id']}/statement?start={(date.today() - timedelta(days=30)).isoformat()}&end={(date.today() - timedelta(days=1)).isoformat()}", headers=h)).json()["data"]
    assert old["lines"] == [] and old["closing_balance"] == old["opening_balance"] == 0
    assert (await ac.get(f"{D}/{d['id']}/statement?start=2026-02-01&end=2026-01-01", headers=h)).status_code == 422


@pytest.mark.asyncio
async def test_performance_target_growth_and_flags(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid = await _product(db_session, seed, price=100, cost=60)
    good, slow, quiet = await _outlet(ac, h), await _outlet(ac, h), await _outlet(ac, h)
    g = (await ac.post(D, headers=h, json={"customer_id": good, "monthly_target": 800})).json()["data"]
    s = (await ac.post(D, headers=h, json={"customer_id": slow, "monthly_target": 100000})).json()["data"]
    q = (await ac.post(D, headers=h, json={"customer_id": quiet})).json()["data"]
    await _deliver(ac, h, good, pid, 10, terms="credit")
    await _deliver(ac, h, slow, pid, 5, terms="credit")
    # Make the slow one's old order late so it is paying late.
    stale = (await db_session.execute(m.FmcgOrder.__table__.select().where(m.FmcgOrder.customer_id == slow))).first()
    await db_session.execute(m.FmcgOrder.__table__.update().where(m.FmcgOrder.id == stale.id).values(due_date=date.today() - timedelta(days=40)))
    await db_session.commit()
    start, end = date.today().replace(day=1).isoformat(), date.today().isoformat()
    p = (await ac.get(f"{D}/{g['id']}/performance?start={start}&end={end}", headers=h)).json()["data"]
    assert p["orders"] == 1 and p["gross_profit"] > 0 and p["flags"] == [] or "behind_target" not in p["flags"]
    assert p["top_products"][0]["units"] == 10 and p["net_sales"] > 0
    ps = (await ac.get(f"{D}/{s['id']}/performance?start={start}&end={end}", headers=h)).json()["data"]
    assert "behind_target" in ps["flags"] and ps["owed_late"] > 0 and "paying_late" in ps["flags"]
    pq = (await ac.get(f"{D}/{q['id']}/performance?start={start}&end={end}", headers=h)).json()["data"]
    assert pq["flags"] == ["no_orders"] and pq["target_pct"] is None
    rank = (await ac.get(f"{D}/ranking?start={start}&end={end}", headers=h)).json()["data"]
    assert [r["distributor_id"] for r in rank][-1] == g["id"] and len(rank) == 3  # needing attention first, the healthy one last
    a = (await ac.post(f"{API}/assistant/ask", headers=h, json={"question": "Which distributors are performing poorly?"})).json()["data"]
    assert a["intent"] == "distributors" and "need attention" in a["answer"]


@pytest.mark.asyncio
async def test_distributor_roles_and_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    o = await _outlet(ac, h)
    d = (await ac.post(D, headers=h, json={"customer_id": o})).json()["data"]
    rep = await _user(ac, db_session, seed, "rep@alpha.example.com", "fmcg_rep")
    assert (await ac.get(D, headers=rep)).status_code == 403
    assert (await ac.post(D, headers=rep, json={"customer_id": o})).status_code == 403
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    other = await _user(ac, db_session, seed, "admin@beta.example.com", "company_admin", tenant="t2", slug="beta")
    assert (await ac.get(f"{D}/{d['id']}/statement", headers=other)).status_code == 404
    assert (await ac.get(f"{D}/{d['id']}/performance", headers=other)).status_code == 404
    assert (await ac.patch(f"{D}/{d['id']}", headers=other, json={"price_discount_pct": 50})).status_code == 404
    assert (await ac.post(D, headers=other, json={"customer_id": o})).status_code == 404
    assert (await ac.get(D, headers=other)).json()["data"] == [] and (await ac.get(f"{D}/ranking", headers=other)).json()["data"] == []
