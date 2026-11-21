"""FMCG warehouse layout: zones, bins, put-away, moves, counts, consumption, pick lists."""

from __future__ import annotations

from datetime import datetime, timedelta
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


async def _user(ac, db_session, seed, email, role, tenant="t1", slug="alpha"):
    db_session.add(m.User(
        tenant_id=seed[tenant].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
        role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug=slug)


async def _warehouse(db_session, seed, tenant="t1"):
    w = m.Warehouse(tenant_id=seed[tenant].id, name="Main", code=f"W{uuid4().hex[:5]}")
    db_session.add(w)
    await db_session.commit()
    return w.id


async def _stock(db_session, seed, lots=(("L1", 100, 200),), name="Rice"):
    p = m.Product(
        tenant_id=seed["t1"].id, name=f"{name} {uuid4().hex[:4]}", sku=f"B{uuid4().hex[:7]}", cost_price=5,
        selling_price=9, stock_qty=sum(q for _, q, _ in lots), is_active=True, tracks_batches=True)
    db_session.add(p)
    await db_session.flush()
    ids = {}
    for number, qty, days in lots:
        b = m.ProductBatch(tenant_id=seed["t1"].id, product_id=p.id, batch_number=number, quantity=qty,
                           expiry_date=datetime.utcnow() + timedelta(days=days))
        db_session.add(b)
        await db_session.flush()
        ids[number] = b.id
    await db_session.commit()
    return SimpleNamespace(id=p.id, batches=ids)


async def _loc(ac, h, wh, kind, code, **extra):
    body = {"warehouse_id": wh, "kind": kind, "code": code, "name": f"{kind} {code}", **extra}
    r = await ac.post(f"{API}/locations", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _layout(ac, h, wh, capacity=60):
    zone = await _loc(ac, h, wh, "zone", "A", zone_type="ambient", pick_order=10)
    quar = await _loc(ac, h, wh, "zone", "Q", zone_type="quarantine", pick_order=900)
    b1 = await _loc(ac, h, wh, "bin", "A-01", parent_id=zone["id"], capacity=capacity)
    b2 = await _loc(ac, h, wh, "bin", "A-02", parent_id=zone["id"], capacity=capacity)
    q1 = await _loc(ac, h, wh, "bin", "Q-01", parent_id=quar["id"])
    return SimpleNamespace(zone=zone, quar=quar, b1=b1, b2=b2, q1=q1)


async def _put(ac, h, bin_id, p, qty, batch=None):
    body = {"bin_id": bin_id, "product_id": p.id, "quantity": qty}
    if batch:
        body["batch_id"] = p.batches[batch]
    return await ac.post(f"{API}/warehouse/put-away", headers=h, json=body)


@pytest.mark.asyncio
async def test_location_rules(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    wh = await _warehouse(db_session, seed)
    lay = await _layout(ac, h, wh)
    dup = await ac.post(f"{API}/locations", headers=h, json={"warehouse_id": wh, "kind": "zone", "code": "a", "name": "Again", "zone_type": "bulk"})
    assert dup.status_code == 409  # codes are case-insensitive per warehouse
    assert (await ac.post(f"{API}/locations", headers=h, json={"warehouse_id": wh, "kind": "bin", "code": "X-1", "name": "No zone"})).status_code == 422
    assert (await ac.post(f"{API}/locations", headers=h, json={"warehouse_id": wh, "kind": "zone", "code": "Z9", "name": "No type"})).status_code == 422
    assert (await ac.post(f"{API}/locations", headers=h, json={"warehouse_id": wh, "kind": "bin", "code": "bad code!", "name": "Bad", "parent_id": lay.zone["id"]})).status_code == 422
    tree = (await ac.get(f"{API}/locations?warehouse_id={wh}", headers=h)).json()["data"]
    assert [z["code"] for z in tree] == ["A", "Q"] and len(tree[0]["bins"]) == 2


@pytest.mark.asyncio
async def test_put_away_limits_capacity_and_unplaced(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    wh = await _warehouse(db_session, seed)
    lay = await _layout(ac, h, wh, capacity=60)
    p = await _stock(db_session, seed, lots=(("L1", 100, 200),))
    assert (await _put(ac, h, lay.b1["id"], p, 70, "L1")).status_code == 409  # over capacity
    r = await _put(ac, h, lay.b1["id"], p, 60, "L1")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["used"] == 60 and r.json()["data"]["utilisation_pct"] == 100.0
    assert (await _put(ac, h, lay.b1["id"], p, 1, "L1")).json()["detail"]["code"] == "BIN_FULL"
    r = await _put(ac, h, lay.b2["id"], p, 50, "L1")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "NOT_ENOUGH_UNPLACED"  # only 40 left
    assert (await _put(ac, h, lay.b2["id"], p, 40, "L1")).status_code == 200
    rep = (await ac.get(f"{API}/warehouse/report", headers=h)).json()["data"]
    assert rep["waiting_for_put_away"] == [] and rep["warehouses"][0]["units_binned"] == 100


@pytest.mark.asyncio
async def test_quarantine_rules(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    wh = await _warehouse(db_session, seed)
    lay = await _layout(ac, h, wh)
    p = await _stock(db_session, seed, lots=(("GOOD", 20, 200), ("OLD", 10, -5), ("BAD", 10, 200)))
    assert (await _put(ac, h, lay.q1["id"], p, 5, "GOOD")).json()["detail"]["code"] == "NOT_QUARANTINED"
    assert (await _put(ac, h, lay.b1["id"], p, 5, "OLD")).json()["detail"]["code"] == "QUARANTINE_ONLY"
    assert (await _put(ac, h, lay.q1["id"], p, 5, "OLD")).status_code == 200
    await ac.post(f"{API}/batches/{p.batches['BAD']}/hold", headers=h, json={"reason": "Lab check pending"})
    assert (await _put(ac, h, lay.b1["id"], p, 5, "BAD")).json()["detail"]["code"] == "QUARANTINE_ONLY"
    assert (await _put(ac, h, lay.q1["id"], p, 5, "BAD")).status_code == 200


@pytest.mark.asyncio
async def test_move_between_bins(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    wh = await _warehouse(db_session, seed)
    lay = await _layout(ac, h, wh, capacity=50)
    p = await _stock(db_session, seed, lots=(("L1", 80, 200),))
    await _put(ac, h, lay.b1["id"], p, 50, "L1")
    body = {"from_bin_id": lay.b1["id"], "to_bin_id": lay.b2["id"], "product_id": p.id, "batch_id": p.batches["L1"], "quantity": 20}
    r = await ac.post(f"{API}/warehouse/move", headers=h, json=body)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["from"]["used"] == 30 and r.json()["data"]["to"]["used"] == 20
    assert (await ac.post(f"{API}/warehouse/move", headers=h, json={**body, "quantity": 31})).json()["detail"]["code"] == "NOT_IN_BIN"
    assert (await ac.post(f"{API}/warehouse/move", headers=h, json={**body, "to_bin_id": lay.b1["id"]})).status_code == 422
    assert (await ac.post(f"{API}/warehouse/move", headers=h, json={**body, "to_bin_id": lay.q1["id"]})).json()["detail"]["code"] == "NOT_QUARANTINED"
    other_wh = await _warehouse(db_session, seed)
    far = await _loc(ac, h, other_wh, "zone", "Z", zone_type="ambient")
    far_bin = await _loc(ac, h, other_wh, "bin", "F-1", parent_id=far["id"])
    assert (await ac.post(f"{API}/warehouse/move", headers=h, json={**body, "to_bin_id": far_bin["id"]})).status_code == 409
    # Stock totals never change from bin work.
    db_session.expire_all()
    assert float((await db_session.get(m.Product, p.id)).stock_qty) == 80


@pytest.mark.asyncio
async def test_delivery_takes_stock_out_of_bins_and_pick_list_follows_expiry(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    wh = await _warehouse(db_session, seed)
    lay = await _layout(ac, h, wh, capacity=100)
    p = await _stock(db_session, seed, lots=(("LATE", 50, 300), ("EARLY", 20, 30)))
    await _put(ac, h, lay.b1["id"], p, 50, "LATE")
    await _put(ac, h, lay.b2["id"], p, 20, "EARLY")
    outlet = (await ac.post(f"{API}/outlets", headers=h, json={"name": "Pick shop"})).json()["data"]["id"]
    order = (await ac.post(f"{API}/orders", headers=h, json={
        "customer_id": outlet, "terms": "credit", "lines": [{"product_id": p.id, "quantity": 30}]})).json()["data"]
    pick = (await ac.get(f"{API}/orders/{order['id']}/pick-list", headers=h)).json()["data"]
    steps = pick["lines"][0]["steps"]
    assert [(s["bin"], s["batch_number"], s["quantity"]) for s in steps] == [("A-02", "EARLY", 20), ("A-01", "LATE", 10)]
    assert pick["lines"][0]["not_in_bins"] == 0
    assert (await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})).status_code == 200
    b1 = (await ac.get(f"{API}/locations/{lay.b1['id']}/contents", headers=h)).json()["data"]
    b2 = (await ac.get(f"{API}/locations/{lay.b2['id']}/contents", headers=h)).json()["data"]
    assert b1["used"] == 40 and b2["used"] == 0
    rep = (await ac.get(f"{API}/warehouse/report", headers=h)).json()["data"]
    assert rep["over_binned"] == []


@pytest.mark.asyncio
async def test_bin_count_variance_needs_reason_and_cannot_exceed_stock(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    wh = await _warehouse(db_session, seed)
    lay = await _layout(ac, h, wh, capacity=200)
    p = await _stock(db_session, seed, lots=(("L1", 100, 200),))
    await _put(ac, h, lay.b1["id"], p, 60, "L1")
    line = {"product_id": p.id, "batch_id": p.batches["L1"], "counted": 55}
    assert (await ac.post(f"{API}/locations/{lay.b1['id']}/count", headers=h, json={"lines": [line]})).status_code == 400
    r = await ac.post(f"{API}/locations/{lay.b1['id']}/count", headers=h, json={"lines": [line], "note": "Five cartons crushed"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["used"] == 55 and r.json()["data"]["variances"][0]["variance"] == -5
    # Found more than the system has unplaced (45 unplaced): refused.
    big = {**line, "counted": 120}
    r = await ac.post(f"{API}/locations/{lay.b1['id']}/count", headers=h, json={"lines": [big], "note": "Found extra"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "MORE_THAN_STOCK"
    # Something missing from the count sheet is counted as zero.
    r = await ac.post(f"{API}/locations/{lay.b1['id']}/count", headers=h, json={"lines": [], "note": "Bin was empty"})
    assert r.status_code == 200 and r.json()["data"]["used"] == 0
    blind = (await ac.get(f"{API}/locations/{lay.b1['id']}/contents?blind=true", headers=h)).json()["data"]
    assert "used" not in blind and all("quantity" not in i for i in blind["items"])
    db_session.expire_all()
    assert float((await db_session.get(m.Product, p.id)).stock_qty) == 100


@pytest.mark.asyncio
async def test_scan_suggest_deactivate_and_report(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    wh = await _warehouse(db_session, seed)
    lay = await _layout(ac, h, wh, capacity=100)
    p = await _stock(db_session, seed, lots=(("L1", 60, 200),))
    sug = (await ac.get(f"{API}/warehouse/suggest?product_id={p.id}&quantity=10&batch_id={p.batches['L1']}", headers=h)).json()["data"]
    assert sug and all(s["code"] != "Q-01" for s in sug)
    await _put(ac, h, lay.b2["id"], p, 30, "L1")
    sug = (await ac.get(f"{API}/warehouse/suggest?product_id={p.id}&quantity=10&batch_id={p.batches['L1']}", headers=h)).json()["data"]
    assert sug[0]["code"] == "A-02" and sug[0]["already_holds_product"] is True
    scanned = (await ac.get(f"{API}/locations/scan?code=a-02", headers=h)).json()["data"]
    assert scanned["id"] == lay.b2["id"] and scanned["items"][0]["quantity"] == 30
    assert (await ac.get(f"{API}/locations/scan?code=NOPE", headers=h)).status_code == 404
    r = await ac.patch(f"{API}/locations/{lay.b2['id']}", headers=h, json={"is_active": False})
    assert r.status_code == 409
    assert (await ac.patch(f"{API}/locations/{lay.zone['id']}", headers=h, json={"is_active": False})).status_code == 409
    assert (await ac.patch(f"{API}/locations/{lay.b1['id']}", headers=h, json={"is_active": False})).status_code == 200
    rep = (await ac.get(f"{API}/warehouse/report", headers=h)).json()["data"]
    assert rep["waiting_for_put_away"][0]["unplaced"] == 30


@pytest.mark.asyncio
async def test_warehouse_roles_and_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    wh = await _warehouse(db_session, seed)
    lay = await _layout(ac, h, wh)
    p = await _stock(db_session, seed)
    await _put(ac, h, lay.b1["id"], p, 10, "L1")
    rep_user = await _user(ac, db_session, seed, "rep@alpha.example.com", "fmcg_rep")
    assert (await ac.get(f"{API}/locations?warehouse_id={wh}", headers=rep_user)).status_code == 403
    assert (await _put(ac, rep_user, lay.b1["id"], p, 1, "L1")).status_code == 403
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    other = await _user(ac, db_session, seed, "admin@beta.example.com", "company_admin", tenant="t2", slug="beta")
    assert (await ac.get(f"{API}/locations?warehouse_id={wh}", headers=other)).status_code == 404
    assert (await ac.get(f"{API}/locations/{lay.b1['id']}/contents", headers=other)).status_code == 404
    assert (await ac.get(f"{API}/locations/scan?code=A-01", headers=other)).status_code == 404
    assert (await ac.post(f"{API}/locations", headers=other, json={"warehouse_id": wh, "kind": "zone", "code": "S", "name": "Steal", "zone_type": "bulk"})).status_code == 404
    assert (await ac.post(f"{API}/warehouse/put-away", headers=other, json={"bin_id": lay.b1["id"], "product_id": p.id, "quantity": 1})).status_code == 404
    assert (await ac.get(f"{API}/warehouse/report", headers=other)).json()["data"]["warehouses"] == []
