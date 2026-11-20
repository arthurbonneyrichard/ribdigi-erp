"""FMCG batches: FEFO delivery, expiry blocking, quarantine, write-off and recall tracing."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _product_with_batches(db_session, seed, lots):
    """lots: list of (batch_number, qty, days_to_expiry)."""
    total = sum(q for _, q, _ in lots)
    p = m.Product(
        tenant_id=seed["t1"].id, name=f"Juice {uuid4().hex[:5]}", sku=f"J{uuid4().hex[:7]}",
        cost_price=5, selling_price=9, stock_qty=total, is_active=True, tracks_batches=True,
    )
    db_session.add(p)
    await db_session.flush()
    ids = {}
    for number, qty, days in lots:
        b = m.ProductBatch(
            tenant_id=seed["t1"].id, product_id=p.id, batch_number=number, quantity=qty,
            expiry_date=datetime.utcnow() + timedelta(days=days),
        )
        db_session.add(b)
        await db_session.flush()
        ids[number] = b.id
    await db_session.commit()
    return SimpleNamespace(id=p.id, batches=ids)


async def _deliver(ac, h, product, qty):
    outlet = (await ac.post(f"{API}/outlets", headers=h, json={"name": f"Shop {uuid4().hex[:5]}"})).json()["data"]["id"]
    order = (
        await ac.post(
            f"{API}/orders", headers=h,
            json={"customer_id": outlet, "terms": "credit", "lines": [{"product_id": product.id, "quantity": qty}]},
        )
    ).json()["data"]
    r = await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})
    return outlet, order, r


@pytest.mark.asyncio
async def test_delivery_takes_earliest_expiry_first_and_records_batches(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product_with_batches(db_session, seed, [("LATE", 50, 200), ("EARLY", 20, 30)])
    _, order, r = await _deliver(ac, h, p, 30)
    assert r.status_code == 200, r.text
    db_session.expire_all()
    assert float((await db_session.get(m.ProductBatch, p.batches["EARLY"])).quantity) == 0
    assert float((await db_session.get(m.ProductBatch, p.batches["LATE"])).quantity) == 40
    rows = (await db_session.execute(select(m.FmcgLineBatch).where(m.FmcgLineBatch.order_id == order["id"]))).scalars().all()
    assert sorted(float(x.quantity) for x in rows) == [10.0, 20.0]


@pytest.mark.asyncio
async def test_expired_and_quarantined_batches_are_never_delivered(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product_with_batches(db_session, seed, [("OLD", 40, -3)])
    _, _, r = await _deliver(ac, h, p, 5)
    assert r.status_code == 409
    q = await _product_with_batches(db_session, seed, [("GOOD", 40, 90)])
    held = await ac.post(f"{API}/batches/{q.batches['GOOD']}/hold", headers=h, json={"reason": "Lab check pending"})
    assert held.status_code == 200, held.text
    _, _, r = await _deliver(ac, h, q, 5)
    assert r.status_code == 409
    assert (await ac.post(f"{API}/batches/{q.batches['GOOD']}/release", headers=h)).status_code == 200
    _, _, r = await _deliver(ac, h, q, 5)
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_batch_list_states_policy_and_validation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _product_with_batches(db_session, seed, [("A", 5, -1), ("B", 5, 10), ("C", 5, 400)])
    data = (await ac.get(f"{API}/batches", headers=h)).json()["data"]
    assert data["counts"] == {"ok": 1, "near": 1, "expired": 1, "held": 0}
    assert len((await ac.get(f"{API}/batches?status=expired", headers=h)).json()["data"]["batches"]) == 1
    assert (await ac.get(f"{API}/batches?status=bogus", headers=h)).status_code == 422
    assert (await ac.put(f"{API}/batch-policy", headers=h, json={"warn_days": [10]})).status_code == 200
    data = (await ac.get(f"{API}/batches", headers=h)).json()["data"]
    assert data["policy"]["warn_days"] == [10] and data["counts"]["near"] == 1
    assert (await ac.put(f"{API}/batch-policy", headers=h, json={"warn_days": [0]})).status_code == 422


@pytest.mark.asyncio
async def test_write_off_posts_loss_and_needs_expiry_or_hold(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product_with_batches(db_session, seed, [("DEAD", 10, -5), ("FINE", 10, 100)])
    r = await ac.post(
        f"{API}/batches/{p.batches['FINE']}/write-off", headers=h,
        json={"quantity": 2, "reason_code": "expiry", "reason": "Not really expired"},
    )
    assert r.status_code == 409
    r = await ac.post(
        f"{API}/batches/{p.batches['FINE']}/write-off", headers=h,
        json={"quantity": 2, "reason_code": "damage", "reason": "Crushed pallet"},
    )
    assert r.status_code == 409 and r.json()["detail"]["code"] == "QUARANTINE_FIRST"
    r = await ac.post(
        f"{API}/batches/{p.batches['DEAD']}/write-off", headers=h,
        json={"quantity": 4, "reason_code": "expiry", "reason": "Past best before date"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["cost"] == 20.0
    db_session.expire_all()
    assert float((await db_session.get(m.ProductBatch, p.batches["DEAD"])).quantity) == 6
    assert float((await db_session.get(m.Product, p.id)).stock_qty) == 16
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)
    r = await ac.post(
        f"{API}/batches/{p.batches['DEAD']}/write-off", headers=h,
        json={"quantity": 99, "reason_code": "expiry", "reason": "Too many"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_recall_traces_outlets_blocks_stock_and_tracks_recovery(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product_with_batches(db_session, seed, [("BAD1", 100, 120)])
    outlet, _, r = await _deliver(ac, h, p, 12)
    assert r.status_code == 200
    r = await ac.post(
        f"{API}/recalls", headers=h,
        json={"title": "Contamination", "reason": "Supplier reported contamination", "batch_ids": [p.batches["BAD1"]]},
    )
    assert r.status_code == 200, r.text
    recall = r.json()["data"]
    b = recall["batches"][0]
    assert b["quantity_delivered"] == 12 and b["quantity_in_stock_now"] == 88
    assert b["outlets"][0]["outlet_id"] == outlet and b["outlets"][0]["quantity"] == 12
    _, _, blocked = await _deliver(ac, h, p, 1)
    assert blocked.status_code == 409
    r = await ac.post(f"{API}/batches/{p.batches['BAD1']}/release", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "BATCH_IN_OPEN_RECALL"
    r = await ac.post(
        f"{API}/recalls/{recall['id']}/recovered", headers=h, json={"batch_id": p.batches["BAD1"], "quantity": 20}
    )
    assert r.status_code == 409
    r = await ac.post(
        f"{API}/recalls/{recall['id']}/recovered", headers=h, json={"batch_id": p.batches["BAD1"], "quantity": 12}
    )
    assert r.json()["data"]["batches"][0]["outstanding"] == 0
    assert (await ac.post(f"{API}/recalls/{recall['id']}/close", headers=h)).status_code == 200
    assert (await ac.post(f"{API}/recalls/{recall['id']}/close", headers=h)).status_code == 409


@pytest.mark.asyncio
async def test_resaleable_return_goes_back_to_its_batch(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product_with_batches(db_session, seed, [("R1", 50, 100)])
    _, order, r = await _deliver(ac, h, p, 10)
    line_id = r.json()["data"]["lines"][0]["id"]
    r = await ac.post(
        f"{API}/orders/{order['id']}/returns", headers=h,
        json={"lines": [{"line_id": line_id, "quantity": 4}], "reason": "unsold", "resaleable": True},
    )
    assert r.status_code == 200, r.text
    db_session.expire_all()
    assert float((await db_session.get(m.ProductBatch, p.batches["R1"])).quantity) == 44


@pytest.mark.asyncio
async def test_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product_with_batches(db_session, seed, [("ISO", 10, 50)])
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    db_session.add(
        m.User(
            tenant_id=seed["t2"].id, email="admin@beta.example.com", full_name="Beta Admin",
            password_hash=hash_password("SecurePass123!"), role="company_admin", email_verified=True,
            permissions=permissions_for_role("company_admin"), totp_enabled=False,
        )
    )
    await db_session.commit()
    other = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    r = await ac.post(f"{API}/batches/{p.batches['ISO']}/hold", headers=other, json={"reason": "Not yours"})
    assert r.status_code == 404
    r = await ac.post(
        f"{API}/recalls", headers=other, json={"title": "Steal", "reason": "Not mine", "batch_ids": [p.batches["ISO"]]}
    )
    assert r.status_code == 404
    assert (await ac.get(f"{API}/batches", headers=other)).json()["data"]["batches"] == []
