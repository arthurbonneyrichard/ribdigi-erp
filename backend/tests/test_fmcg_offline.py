"""FMCG offline sync: each reference saves once, every rule still applies, one bad item never blocks the rest."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"
SYNC = f"{API}/offline/sync"
PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()


def _ref():
    return f"dev-{uuid4().hex}"


def _at(minutes=-5):
    return (datetime.utcnow() + timedelta(minutes=minutes)).isoformat()


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _user(db_session, seed, role, tenant="t1"):
    u = m.User(tenant_id=seed[tenant].id, email=f"{role}-{uuid4().hex[:4]}@alpha.example.com", full_name=role, password_hash=hash_password("SecurePass123!"),
               role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False)
    db_session.add(u)
    await db_session.commit()
    return u.email, u.id


async def _world(ac, h, db_session, seed):
    p = m.Product(tenant_id=seed["t1"].id, name=f"Rice {uuid4().hex[:4]}", sku=f"O{uuid4().hex[:7]}", cost_price=5, selling_price=9, stock_qty=100, is_active=True, tracks_batches=False)
    db_session.add(p)
    await db_session.commit()
    outlet = (await ac.post(f"{API}/outlets", headers=h, json={"name": f"Shop {uuid4().hex[:4]}"})).json()["data"]["id"]
    assert (await ac.put(f"{API}/merch/must-stock", headers=h, json={"items": [{"product_id": p.id, "min_facings": 1}]})).status_code == 200
    return p.id, outlet


def _audit(outlet, pid, **extra):
    return {"outlet_id": outlet, "lines": [{"product_id": pid, "present": True, "facings": 2}], **extra}


async def _send(ac, h, *actions):
    r = await ac.post(SYNC, headers=h, json={"actions": list(actions)})
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_a_reference_saves_once_even_when_sent_again(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid, outlet = await _world(ac, h, db_session, seed)
    a = {"ref": _ref(), "kind": "shelf_audit", "captured_at": _at(-30), "payload": _audit(outlet, pid)}
    first = await _send(ac, h, a)
    assert first["saved"] == 1 and first["results"][0]["status"] == "ok"
    again = await _send(ac, h, a)  # the phone never heard the reply and retries
    assert again["duplicates"] == 1 and again["results"][0]["status"] == "duplicate" and again["results"][0]["result_id"] == first["results"][0]["result_id"]
    same_batch = await _send(ac, h, {**a, "ref": _ref()}, {**a, "ref": a["ref"]})
    assert [r["status"] for r in same_batch["results"]] == ["ok", "duplicate"]
    audits = (await db_session.execute(select(func.count()).select_from(m.FmcgShelfAudit))).scalar_one()
    assert audits == 2  # the original and the one new reference


@pytest.mark.asyncio
async def test_the_time_it_was_really_taken_is_kept(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid, outlet = await _world(ac, h, db_session, seed)
    taken = datetime.utcnow() - timedelta(hours=5)
    out = await _send(ac, h, {"ref": _ref(), "kind": "shelf_audit", "captured_at": taken.isoformat(), "payload": _audit(outlet, pid)})
    audit = (await ac.get(f"{API}/merch/audits/{out['results'][0]['result_id']}", headers=h)).json()["data"]
    assert audit["audited_at"][:16] == taken.isoformat()[:16]


@pytest.mark.asyncio
async def test_all_four_kinds_save_and_the_rules_still_apply(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid, outlet = await _world(ac, h, db_session, seed)
    order = (await ac.post(f"{API}/orders", headers=h, json={"customer_id": outlet, "terms": "credit", "lines": [{"product_id": pid, "quantity": 2}]})).json()["data"]
    booked_only = {"ref": _ref(), "kind": "pod", "captured_at": _at(), "payload": {"order_id": order["id"], "recipient_name": "Ama Mensah", "signature": PNG}}
    r = (await _send(ac, h, booked_only))["results"][0]
    assert r["status"] == "failed" and "delivered" in r["message"]
    assert (await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})).status_code == 200
    out = await _send(
        ac, h, {**booked_only, "ref": _ref()},
        {"ref": _ref(), "kind": "complaint", "captured_at": _at(), "payload": {"category": "quality", "description": "Bottles taste flat", "order_id": order["id"], "product_id": pid}},
        {"ref": _ref(), "kind": "competitor_price", "captured_at": _at(), "payload": {"product_id": pid, "competitor_brand": "Rival", "competitor_product": "Rival Rice", "price": 8.5}},
        {"ref": _ref(), "kind": "shelf_audit", "captured_at": _at(), "payload": _audit(outlet, pid)},
    )
    assert [r["status"] for r in out["results"]] == ["ok"] * 4 and out["saved"] == 4
    assert (await ac.get(f"{API}/orders/{order['id']}/pod", headers=h)).json()["data"]["recipient_name"] == "Ama Mensah"
    # An incomplete shelf audit is refused with the reason, exactly as when sent live.
    bad = (await _send(ac, h, {"ref": _ref(), "kind": "shelf_audit", "captured_at": _at(), "payload": {"outlet_id": outlet, "lines": []}}))["results"][0]
    assert bad["status"] == "failed" and "must-stock" in bad["message"].lower()
    invalid = (await _send(ac, h, {"ref": _ref(), "kind": "competitor_price", "captured_at": _at(), "payload": {"product_id": pid, "price": -1}}))["results"][0]
    assert invalid["status"] == "failed" and invalid["message"].startswith("Invalid")


@pytest.mark.asyncio
async def test_one_failure_never_blocks_the_rest_and_a_failed_ref_can_be_retried(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid, outlet = await _world(ac, h, db_session, seed)
    good, bad, retry = _ref(), _ref(), _ref()
    out = await _send(
        ac, h,
        {"ref": bad, "kind": "complaint", "captured_at": _at(), "payload": {"category": "quality", "description": "Broken", "batch_id": str(uuid4()), "product_id": pid}},
        {"ref": good, "kind": "complaint", "captured_at": _at(), "payload": {"category": "other", "description": "Late delivery"}},
        {"ref": retry, "kind": "shelf_audit", "captured_at": _at(), "payload": _audit(str(uuid4()), pid)},
    )
    assert [r["status"] for r in out["results"]] == ["failed", "ok", "failed"] and out["saved"] == 1 and out["failed"] == 2
    complaints = (await db_session.execute(select(func.count()).select_from(m.FmcgComplaint))).scalar_one()
    assert complaints == 1  # the failed one left nothing behind
    # The same reference sent again with corrected data is retried, not refused as a duplicate.
    fixed = (await _send(ac, h, {"ref": retry, "kind": "shelf_audit", "captured_at": _at(), "payload": _audit(outlet, pid)}))["results"][0]
    assert fixed["status"] == "ok"
    log = (await ac.get(f"{API}/offline/log", headers=h)).json()["data"]
    states = {x["ref"]: x["status"] for x in log}
    assert states[good] == "ok" and states[bad] == "failed" and states[retry] == "ok"


@pytest.mark.asyncio
async def test_old_future_and_malformed_items_are_refused(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid, outlet = await _world(ac, h, db_session, seed)
    ok_payload = {"category": "other", "description": "Late delivery"}
    old = (await _send(ac, h, {"ref": _ref(), "kind": "complaint", "captured_at": _at(-73 * 60), "payload": ok_payload}))["results"][0]
    assert old["status"] == "failed" and "72 hours" in old["message"]
    future = (await _send(ac, h, {"ref": _ref(), "kind": "complaint", "captured_at": _at(+120), "payload": ok_payload}))["results"][0]
    assert future["status"] == "failed" and "future" in future["message"]
    assert (await ac.post(SYNC, headers=h, json={"actions": []})).status_code == 422
    assert (await ac.post(SYNC, headers=h, json={"actions": [{"ref": "x", "kind": "complaint", "captured_at": _at(), "payload": {}}]})).status_code == 422
    assert (await ac.post(SYNC, headers=h, json={"actions": [{"ref": _ref(), "kind": "delete_everything", "captured_at": _at(), "payload": {}}]})).status_code == 422
    assert (await ac.post(SYNC, headers=h, json={"actions": [{"ref": _ref(), "kind": "complaint", "captured_at": _at(), "payload": {}} for _ in range(51)]})).status_code == 422
    assert (await ac.post(SYNC, headers=h, json={"actions": [{"ref": _ref(), "kind": "complaint", "captured_at": _at(), "payload": ok_payload, "extra": 1}]})).status_code == 422


@pytest.mark.asyncio
async def test_roles_territory_and_own_log(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid, outlet = await _world(ac, h, db_session, seed)
    email, rep_id = await _user(db_session, seed, "fmcg_rep")
    rep = await auth_headers(ac, email=email, tenant_slug="alpha")
    # A rep may not sync an audit for an outlet outside their territory, but may sync a complaint.
    out = await _send(
        ac, rep,
        {"ref": _ref(), "kind": "shelf_audit", "captured_at": _at(), "payload": _audit(outlet, pid)},
        {"ref": _ref(), "kind": "complaint", "captured_at": _at(), "payload": {"category": "other", "description": "Outlet closed early"}},
        {"ref": _ref(), "kind": "pod", "captured_at": _at(), "payload": {"order_id": str(uuid4()), "recipient_name": "Someone", "signature": PNG}},
    )
    assert [r["status"] for r in out["results"]] == ["failed", "ok", "failed"]
    assert "territory" in out["results"][0]["message"].lower()
    # A storekeeper has none of these jobs.
    sk_email, _ = await _user(db_session, seed, "fmcg_storekeeper")
    sk = await auth_headers(ac, email=sk_email, tenant_slug="alpha")
    r = (await _send(ac, sk, {"ref": _ref(), "kind": "complaint", "captured_at": _at(), "payload": {"category": "other", "description": "Not my job"}}))["results"][0]
    assert r["status"] == "failed"
    mine = (await ac.get(f"{API}/offline/log", headers=rep)).json()["data"]
    assert len(mine) == 3 and all(x["ref"] for x in mine)
    assert len((await ac.get(f"{API}/offline/log", headers=h)).json()["data"]) == 4  # a manager sees everyone's


@pytest.mark.asyncio
async def test_offline_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid, outlet = await _world(ac, h, db_session, seed)
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    email, _ = await _user(db_session, seed, "company_admin", tenant="t2")
    other = await auth_headers(ac, email=email, tenant_slug="beta")
    shared = _ref()
    # The same reference in another company is its own item, and cannot touch this company's records.
    out = await _send(
        ac, other,
        {"ref": shared, "kind": "shelf_audit", "captured_at": _at(), "payload": _audit(outlet, pid)},
        {"ref": _ref(), "kind": "competitor_price", "captured_at": _at(), "payload": {"product_id": pid, "competitor_brand": "Rival", "competitor_product": "Rice", "price": 5}},
    )
    assert [r["status"] for r in out["results"]] == ["failed", "failed"]
    mine = await _send(ac, h, {"ref": shared, "kind": "shelf_audit", "captured_at": _at(), "payload": _audit(outlet, pid)})
    assert mine["results"][0]["status"] == "ok"
    assert (await ac.get(f"{API}/offline/log", headers=other)).json()["data"][-1]["status"] == "failed"
    assert all(x["status"] == "failed" for x in (await ac.get(f"{API}/offline/log", headers=other)).json()["data"])
