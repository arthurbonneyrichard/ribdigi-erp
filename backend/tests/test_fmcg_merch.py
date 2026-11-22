"""FMCG merchandising: must-stock list, shelf audits, territory rule, competitor prices, report."""

from __future__ import annotations

import base64
from uuid import uuid4

import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"
M = f"{API}/merch"
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _user(ac, db_session, seed, email, role, tenant="t1", slug="alpha"):
    u = m.User(tenant_id=seed[tenant].id, email=email, full_name=f"{role} person", password_hash=hash_password("SecurePass123!"),
               role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False)
    db_session.add(u)
    await db_session.commit()
    return u.id, await auth_headers(ac, email=email, tenant_slug=slug)


async def _product(db_session, seed, name, price=10):
    p = m.Product(tenant_id=seed["t1"].id, name=f"{name} {uuid4().hex[:4]}", sku=f"M{uuid4().hex[:7]}", cost_price=5,
                  selling_price=price, stock_qty=100, is_active=True, tracks_batches=False)
    db_session.add(p)
    await db_session.commit()
    return p.id


async def _outlet(ac, h, route_id=None):
    body = {"name": f"Kiosk {uuid4().hex[:4]}"}
    if route_id:
        body["route_id"] = route_id
    return (await ac.post(f"{API}/outlets", headers=h, json=body)).json()["data"]["id"]


async def _setup(ac, h, db_session, seed):
    a = await _product(db_session, seed, "Soap")
    b = await _product(db_session, seed, "Rice")
    c = await _product(db_session, seed, "Oil")
    r = await ac.put(f"{M}/must-stock", headers=h, json={"items": [{"product_id": a, "min_facings": 2}, {"product_id": b, "min_facings": 1}]})
    assert r.status_code == 200, r.text
    return a, b, c


@pytest.mark.asyncio
async def test_must_stock_list_rules(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, b, c = await _setup(ac, h, db_session, seed)
    assert len((await ac.get(f"{M}/must-stock", headers=h)).json()["data"]) == 2
    r = await ac.put(f"{M}/must-stock", headers=h, json={"items": [{"product_id": a}, {"product_id": a}]})
    assert r.status_code == 422
    assert (await ac.put(f"{M}/must-stock", headers=h, json={"items": [{"product_id": str(uuid4())}]})).status_code == 404
    r = await ac.put(f"{M}/must-stock", headers=h, json={"items": [{"product_id": b, "min_facings": 3}]})
    assert [(x["product_id"], x["min_facings"]) for x in r.json()["data"]] == [(b, 3)]  # replaces the whole list


@pytest.mark.asyncio
async def test_audit_must_be_complete_and_is_scored(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, b, c = await _setup(ac, h, db_session, seed)
    outlet = await _outlet(ac, h)
    base = {"outlet_id": outlet}
    r = await ac.post(f"{M}/audits", headers=h, json={**base, "lines": [{"product_id": a, "present": True, "facings": 2}]})
    assert r.status_code == 422 and r.json()["detail"]["code"] == "MUST_STOCK_INCOMPLETE" and "Rice" in r.json()["detail"]["message"]
    bad = await ac.post(f"{M}/audits", headers=h, json={**base, "lines": [
        {"product_id": a, "present": True, "facings": 0}, {"product_id": b, "present": False, "facings": 0}]})
    assert bad.status_code == 422
    bad = await ac.post(f"{M}/audits", headers=h, json={**base, "lines": [
        {"product_id": a, "present": False, "facings": 2}, {"product_id": b, "present": False, "facings": 0}]})
    assert bad.status_code == 422
    r = await ac.post(f"{M}/audits", headers=h, json={**base, "display_ok": True, "photo": PNG, "notes": "Neat shelf", "lines": [
        {"product_id": a, "present": True, "facings": 1, "shelf_price": 11},  # on shelf but under the 2 facings required
        {"product_id": b, "present": True, "facings": 3},
        {"product_id": c, "present": True, "facings": 1}]})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["required"] == 2 and d["available"] == 2 and d["compliant"] == 1 and d["score_pct"] == 50.0
    full = (await ac.get(f"{M}/audits/{d['id']}", headers=h)).json()["data"]
    assert full["photo"] == PNG and len(full["lines"]) == 3
    soap = [l for l in full["lines"] if l["product_id"] == a][0]
    assert soap["must_stock"] is True and soap["shelf_price"] == 11 and soap["min_facings"] == 2
    fake = "data:image/png;base64," + base64.b64encode(b"nope").decode()
    assert (await ac.post(f"{M}/audits", headers=h, json={**base, "photo": fake, "lines": [
        {"product_id": a, "present": True, "facings": 2}, {"product_id": b, "present": True, "facings": 1}]})).status_code == 422


@pytest.mark.asyncio
async def test_rep_can_only_audit_own_territory_and_sees_own_audits(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, b, c = await _setup(ac, h, db_session, seed)
    route = (await ac.post(f"{API}/routes", headers=h, json={"code": f"R{uuid4().hex[:4]}", "name": "North"})).json()["data"]
    mine, other = await _outlet(ac, h, route["id"]), await _outlet(ac, h)
    rep_id, rep = await _user(ac, db_session, seed, "rep@alpha.example.com", "fmcg_rep")
    terr = await ac.post(f"{API}/territories", headers=h, json={"code": f"T{uuid4().hex[:4]}", "name": "Zone", "route_ids": [route["id"]], "rep_user_ids": [rep_id]})
    assert terr.status_code == 200, terr.text
    lines = [{"product_id": a, "present": True, "facings": 2}, {"product_id": b, "present": True, "facings": 1}]
    r = await ac.post(f"{M}/audits", headers=rep, json={"outlet_id": other, "lines": lines})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "OUTSIDE_TERRITORY"
    r = await ac.post(f"{M}/audits", headers=rep, json={"outlet_id": mine, "lines": lines})
    assert r.status_code == 200, r.text
    await ac.post(f"{M}/audits", headers=h, json={"outlet_id": other, "lines": lines})  # a manager's own audit
    assert len((await ac.get(f"{M}/audits", headers=rep)).json()["data"]) == 1
    assert len((await ac.get(f"{M}/audits", headers=h)).json()["data"]) == 2
    mgr_audit = [x for x in (await ac.get(f"{M}/audits", headers=h)).json()["data"] if x["outlet_id"] == other][0]
    assert (await ac.get(f"{M}/audits/{mgr_audit['id']}", headers=rep)).status_code == 404
    # A rep cannot change the list or read manager reports.
    assert (await ac.put(f"{M}/must-stock", headers=rep, json={"items": []})).status_code == 403
    assert (await ac.get(f"{M}/report", headers=rep)).status_code == 403
    # Visit link must be the rep's own visit at this outlet.
    other_visit = m.FmcgVisit(tenant_id=seed["t1"].id, outlet_id=other, user_id=rep_id, checked_in_at=__import__("datetime").datetime.utcnow())
    db_session.add(other_visit)
    await db_session.commit()
    r = await ac.post(f"{M}/audits", headers=rep, json={"outlet_id": mine, "visit_id": other_visit.id, "lines": lines})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_competitor_prices_and_report(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, b, c = await _setup(ac, h, db_session, seed)
    o1, o2, never = await _outlet(ac, h), await _outlet(ac, h), await _outlet(ac, h)
    ok = [{"product_id": a, "present": True, "facings": 2, "shelf_price": 12}, {"product_id": b, "present": True, "facings": 1}]
    gap = [{"product_id": a, "present": False, "facings": 0}, {"product_id": b, "present": True, "facings": 1}]
    await ac.post(f"{M}/audits", headers=h, json={"outlet_id": o1, "lines": ok})
    await ac.post(f"{M}/audits", headers=h, json={"outlet_id": o2, "lines": gap})
    for price in (8, 12):
        r = await ac.post(f"{M}/competitor-prices", headers=h, json={"product_id": a, "competitor_brand": "Rival", "competitor_product": "Rival Soap", "price": price})
        assert r.status_code == 200, r.text
    assert (await ac.post(f"{M}/competitor-prices", headers=h, json={"product_id": a, "competitor_brand": "Rival", "competitor_product": "Soap", "price": 0})).status_code == 422
    assert (await ac.post(f"{M}/competitor-prices", headers=h, json={"product_id": str(uuid4()), "competitor_brand": "Rival", "competitor_product": "Soap", "price": 5})).status_code == 404
    rep = (await ac.get(f"{M}/report", headers=h)).json()["data"]
    s = rep["summary"]
    assert s["audits"] == 2 and s["outlets_audited"] == 2 and s["average_score_pct"] == 75.0 and s["active_outlets"] >= 3
    assert rep["outlets"][0]["score_pct"] == 50.0  # worst first
    soap = [p for p in rep["products"] if p["product_id"] == a][0]
    assert soap["availability_pct"] == 50.0 and soap["out_of_stock_at"] == 1
    price = rep["prices"][0]
    assert price["product_id"] == a and price["competitor_avg"] == 10.0 and price["price_index"] == 100.0  # list price 10 vs avg 10
    assert price["our_shelf_price_avg"] == 12.0 and price["competitor_low"] == 8 and price["competitor_high"] == 12
    assert len((await ac.get(f"{M}/competitor-prices", headers=h)).json()["data"]) == 2
    assert (await ac.get(f"{M}/report?start=2026-02-01&end=2026-01-01", headers=h)).status_code == 422


@pytest.mark.asyncio
async def test_merch_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, b, c = await _setup(ac, h, db_session, seed)
    outlet = await _outlet(ac, h)
    lines = [{"product_id": a, "present": True, "facings": 2}, {"product_id": b, "present": True, "facings": 1}]
    audit = (await ac.post(f"{M}/audits", headers=h, json={"outlet_id": outlet, "lines": lines})).json()["data"]
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    _, other = await _user(ac, db_session, seed, "admin@beta.example.com", "company_admin", tenant="t2", slug="beta")
    assert (await ac.get(f"{M}/audits/{audit['id']}", headers=other)).status_code == 404
    assert (await ac.post(f"{M}/audits", headers=other, json={"outlet_id": outlet, "lines": []})).status_code == 404
    assert (await ac.put(f"{M}/must-stock", headers=other, json={"items": [{"product_id": a}]})).status_code == 404
    assert (await ac.post(f"{M}/competitor-prices", headers=other, json={"product_id": a, "competitor_brand": "Rival", "competitor_product": "Soap", "price": 5})).status_code == 404
    assert (await ac.get(f"{M}/must-stock", headers=other)).json()["data"] == []
    assert (await ac.get(f"{M}/audits", headers=other)).json()["data"] == []
    rep = (await ac.get(f"{M}/report", headers=other)).json()["data"]
    assert rep["summary"]["audits"] == 0 and rep["products"] == [] and rep["prices"] == []
