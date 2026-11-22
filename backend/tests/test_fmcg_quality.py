"""FMCG quality: proof of delivery, inspections that hold batches, complaints."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()
JPG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0" + b"0" * 64).decode()


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _user(ac, db_session, seed, email, role, tenant="t1", slug="alpha"):
    db_session.add(m.User(
        tenant_id=seed[tenant].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
        role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug=slug)


async def _stock(db_session, seed, lots=(("L1", 50, 120),)):
    p = m.Product(
        tenant_id=seed["t1"].id, name=f"Cola {uuid4().hex[:5]}", sku=f"Q{uuid4().hex[:7]}",
        cost_price=5, selling_price=9, stock_qty=sum(q for _, q, _ in lots), is_active=True, tracks_batches=True)
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


async def _delivered_order(ac, h, p, qty=5):
    outlet = (await ac.post(f"{API}/outlets", headers=h, json={"name": f"Shop {uuid4().hex[:5]}"})).json()["data"]["id"]
    order = (await ac.post(f"{API}/orders", headers=h, json={
        "customer_id": outlet, "terms": "credit", "lines": [{"product_id": p.id, "quantity": qty}]})).json()["data"]
    r = await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})
    assert r.status_code == 200, r.text
    return outlet, order["id"]


@pytest.mark.asyncio
async def test_proof_of_delivery_rules(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _stock(db_session, seed)
    outlet = (await ac.post(f"{API}/outlets", headers=h, json={"name": "Not yet"})).json()["data"]["id"]
    booked = (await ac.post(f"{API}/orders", headers=h, json={
        "customer_id": outlet, "terms": "credit", "lines": [{"product_id": p.id, "quantity": 1}]})).json()["data"]
    r = await ac.post(f"{API}/orders/{booked['id']}/pod", headers=h, json={"recipient_name": "Ama", "signature": PNG})
    assert r.status_code == 409
    _, oid = await _delivered_order(ac, h, p)
    miss = (await ac.get(f"{API}/pod/missing", headers=h)).json()["data"]
    assert any(x["order_id"] == oid for x in miss)
    assert (await ac.get(f"{API}/orders/{oid}/pod", headers=h)).status_code == 404
    assert (await ac.post(f"{API}/orders/{oid}/pod", headers=h, json={"recipient_name": "Ama"})).status_code == 422
    bad = await ac.post(f"{API}/orders/{oid}/pod", headers=h, json={"recipient_name": "Ama", "signature": "data:text/html;base64,AAAA"})
    assert bad.status_code == 422
    fake = "data:image/png;base64," + base64.b64encode(b"not a png at all").decode()
    assert (await ac.post(f"{API}/orders/{oid}/pod", headers=h, json={"recipient_name": "Ama", "signature": fake})).status_code == 422
    big = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 200_000).decode()
    assert (await ac.post(f"{API}/orders/{oid}/pod", headers=h, json={"recipient_name": "Ama", "signature": big})).status_code == 413
    ok = await ac.post(f"{API}/orders/{oid}/pod", headers=h, json={
        "recipient_name": "Ama Mensah", "signature": PNG, "photo": JPG, "latitude": 5.6, "longitude": -0.19, "accuracy_m": 12})
    assert ok.status_code == 200, ok.text
    assert (await ac.post(f"{API}/orders/{oid}/pod", headers=h, json={"recipient_name": "Again", "signature": PNG})).status_code == 409
    got = (await ac.get(f"{API}/orders/{oid}/pod", headers=h)).json()["data"]
    assert got["signature"] == PNG and got["has_photo"] is True and got["recipient_name"] == "Ama Mensah"
    assert all(x["order_id"] != oid for x in (await ac.get(f"{API}/pod/missing", headers=h)).json()["data"])


@pytest.mark.asyncio
async def test_inspection_holds_batch_until_decided(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _stock(db_session, seed)
    r = await ac.post(f"{API}/quality/inspections", headers=h, json={
        "product_id": p.id, "batch_id": p.batches["L1"], "packaging_ok": True, "label_ok": True, "expiry_ok": True,
        "temperature_c": 4.5, "hold_until_decided": True})
    assert r.status_code == 200, r.text
    ins = r.json()["data"]
    assert ins["held"] is True and ins["status"] == "pending"
    _, _ = None, None
    outlet = (await ac.post(f"{API}/outlets", headers=h, json={"name": "Held shop"})).json()["data"]["id"]
    order = (await ac.post(f"{API}/orders", headers=h, json={
        "customer_id": outlet, "terms": "credit", "lines": [{"product_id": p.id, "quantity": 2}]})).json()["data"]
    assert (await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})).status_code == 409
    r = await ac.post(f"{API}/quality/inspections/{ins['id']}/decide", headers=h, json={"result": "pass"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "passed"
    assert (await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})).status_code == 200
    assert (await ac.post(f"{API}/quality/inspections/{ins['id']}/decide", headers=h, json={"result": "pass"})).status_code == 409


@pytest.mark.asyncio
async def test_failed_inspection_keeps_batch_held_and_rules(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _stock(db_session, seed)
    r = await ac.post(f"{API}/quality/inspections", headers=h, json={
        "product_id": p.id, "batch_id": p.batches["L1"], "packaging_ok": False})
    ins = r.json()["data"]
    assert ins["held"] is False
    r = await ac.post(f"{API}/quality/inspections/{ins['id']}/decide", headers=h, json={"result": "pass"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "CHECK_FAILED"
    assert (await ac.post(f"{API}/quality/inspections/{ins['id']}/decide", headers=h, json={"result": "fail"})).status_code == 422
    r = await ac.post(f"{API}/quality/inspections/{ins['id']}/decide", headers=h,
                      json={"result": "fail", "note": "Crushed cartons", "rejected_qty": 999})
    assert r.status_code == 409
    r = await ac.post(f"{API}/quality/inspections/{ins['id']}/decide", headers=h,
                      json={"result": "fail", "note": "Crushed cartons", "rejected_qty": 10})
    assert r.status_code == 200 and r.json()["data"]["status"] == "failed" and r.json()["data"]["held"] is True
    batches = (await ac.get(f"{API}/batches?status=held", headers=h)).json()["data"]["batches"]
    assert [b["id"] for b in batches] == [p.batches["L1"]]


@pytest.mark.asyncio
async def test_inspection_does_not_release_a_recall_hold(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _stock(db_session, seed)
    rec = await ac.post(f"{API}/recalls", headers=h, json={
        "title": "Recall", "reason": "Supplier alert", "batch_ids": [p.batches["L1"]]})
    assert rec.status_code == 200
    ins = (await ac.post(f"{API}/quality/inspections", headers=h, json={
        "product_id": p.id, "batch_id": p.batches["L1"], "hold_until_decided": True})).json()["data"]
    assert ins["held"] is False
    await ac.post(f"{API}/quality/inspections/{ins['id']}/decide", headers=h, json={"result": "pass"})
    assert len((await ac.get(f"{API}/batches?status=held", headers=h)).json()["data"]["batches"]) == 1


@pytest.mark.asyncio
async def test_supplier_history_and_validation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _stock(db_session, seed)
    sup = m.Party(tenant_id=seed["t1"].id, kind="supplier", name="Fresh Foods Ltd")
    db_session.add(sup)
    await db_session.commit()
    for result, note in (("pass", None), ("fail", "Wrong label"), ("fail", "Warm delivery")):
        ins = (await ac.post(f"{API}/quality/inspections", headers=h, json={"product_id": p.id, "supplier_id": sup.id})).json()["data"]
        r = await ac.post(f"{API}/quality/inspections/{ins['id']}/decide", headers=h, json={"result": result, **({"note": note} if note else {})})
        assert r.status_code == 200, r.text
    hist = (await ac.get(f"{API}/quality/suppliers", headers=h)).json()["data"]
    assert hist[0]["supplier"] == "Fresh Foods Ltd" and hist[0]["failed"] == 2 and hist[0]["fail_rate_pct"] == 66.7
    r = await ac.post(f"{API}/quality/inspections", headers=h, json={"product_id": p.id, "supplier_id": str(uuid4())})
    assert r.status_code == 404
    r = await ac.post(f"{API}/quality/inspections", headers=h, json={"product_id": p.id, "hold_until_decided": True})
    assert r.status_code == 422
    assert len((await ac.get(f"{API}/quality/inspections?status=failed", headers=h)).json()["data"]) == 2


@pytest.mark.asyncio
async def test_complaints_flow_and_roles(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _stock(db_session, seed)
    outlet, oid = await _delivered_order(ac, h, p)
    rep = await _user(ac, db_session, seed, "rep@alpha.example.com", "fmcg_rep")
    r = await ac.post(f"{API}/complaints", headers=rep, json={
        "order_id": oid, "product_id": p.id, "batch_id": p.batches["L1"], "category": "quality",
        "description": "Bottles taste flat"})
    assert r.status_code == 200, r.text
    c1 = r.json()["data"]
    assert c1["customer_id"] == outlet and c1["batch_number"] == "L1"
    c2 = (await ac.post(f"{API}/complaints", headers=h, json={
        "product_id": p.id, "batch_id": p.batches["L1"], "category": "quality", "description": "Also flat"})).json()["data"]
    assert c2["complaints_on_this_batch"] == 2
    r = await ac.post(f"{API}/complaints", headers=h, json={"batch_id": p.batches["L1"], "category": "quality", "description": "No product"})
    assert r.status_code == 422
    assert (await ac.post(f"{API}/complaints/{c1['id']}/status", headers=rep, json={"status": "investigating"})).status_code == 403
    assert (await ac.get(f"{API}/quality/inspections", headers=rep)).status_code == 403
    assert (await ac.post(f"{API}/complaints/{c1['id']}/status", headers=h, json={"status": "resolved"})).status_code == 400
    r = await ac.post(f"{API}/complaints/{c1['id']}/status", headers=h, json={"status": "resolved", "resolution": "Replaced the stock"})
    assert r.status_code == 200 and r.json()["data"]["status"] == "resolved"
    assert (await ac.post(f"{API}/complaints/{c1['id']}/status", headers=h, json={"status": "investigating"})).status_code == 409
    assert len((await ac.get(f"{API}/complaints?status=open", headers=h)).json()["data"]) == 1


@pytest.mark.asyncio
async def test_quality_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _stock(db_session, seed)
    _, oid = await _delivered_order(ac, h, p)
    await ac.post(f"{API}/orders/{oid}/pod", headers=h, json={"recipient_name": "Ama Mensah", "signature": PNG})
    ins = (await ac.post(f"{API}/quality/inspections", headers=h, json={"product_id": p.id})).json()["data"]
    comp = (await ac.post(f"{API}/complaints", headers=h, json={"category": "other", "description": "Just a note"})).json()["data"]
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    other = await _user(ac, db_session, seed, "admin@beta.example.com", "company_admin", tenant="t2", slug="beta")
    assert (await ac.get(f"{API}/orders/{oid}/pod", headers=other)).status_code == 404
    assert (await ac.post(f"{API}/orders/{oid}/pod", headers=other, json={"recipient_name": "Thief", "signature": PNG})).status_code == 404
    assert (await ac.post(f"{API}/quality/inspections/{ins['id']}/decide", headers=other, json={"result": "pass"})).status_code == 404
    assert (await ac.post(f"{API}/complaints/{comp['id']}/status", headers=other, json={"status": "investigating"})).status_code == 404
    assert (await ac.post(f"{API}/quality/inspections", headers=other, json={"product_id": p.id})).status_code == 404
    assert (await ac.get(f"{API}/complaints", headers=other)).json()["data"] == []
    assert (await ac.get(f"{API}/pod/missing", headers=other)).json()["data"] == []
