"""FMCG staff roles: storekeeper, quality officer and fleet manager each get only their own jobs."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app import models as m
from app.rbac import ROLE_LABELS, permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"
ROLES = ("fmcg_storekeeper", "fmcg_quality", "fmcg_fleet")


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _staff(ac, db_session, seed, role):
    email = f"{role}@alpha.example.com"
    db_session.add(m.User(tenant_id=seed["t1"].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
                          role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug="alpha")


async def _batch(db_session, seed):
    p = m.Product(tenant_id=seed["t1"].id, name=f"Cola {uuid4().hex[:4]}", sku=f"Z{uuid4().hex[:7]}", cost_price=5, selling_price=9,
                  stock_qty=20, is_active=True, tracks_batches=True)
    db_session.add(p)
    await db_session.flush()
    b = m.ProductBatch(tenant_id=seed["t1"].id, product_id=p.id, batch_number="ZB1", quantity=20, expiry_date=datetime.utcnow() + timedelta(days=90))
    db_session.add(b)
    await db_session.commit()
    return p.id, b.id


def test_roles_exist_with_labels():
    for role in ROLES:
        assert role in ROLE_LABELS and permissions_for_role(role)["fmcg"] == ["read", "write"]
    assert ROLE_LABELS["fmcg_storekeeper"] == "Storekeeper" and ROLE_LABELS["fmcg_fleet"] == "Fleet Manager"


@pytest.mark.asyncio
async def test_storekeeper_runs_the_warehouse_and_sees_batches_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    pid, bid = await _batch(db_session, seed)
    sk = await _staff(ac, db_session, seed, "fmcg_storekeeper")
    wh = m.Warehouse(tenant_id=seed["t1"].id, name="Main", code=f"W{uuid4().hex[:4]}")
    db_session.add(wh)
    await db_session.commit()
    zone = (await ac.post(f"{API}/locations", headers=sk, json={"warehouse_id": wh.id, "kind": "zone", "code": "A", "name": "Zone A", "zone_type": "ambient"}))
    assert zone.status_code == 200, zone.text
    assert (await ac.get(f"{API}/warehouse/report", headers=sk)).status_code == 200
    assert (await ac.get(f"{API}/batches", headers=sk)).status_code == 200
    for method, path, body in (
        ("post", f"/batches/{bid}/hold", {"reason": "Lab check pending"}),
        ("post", f"/batches/{bid}/write-off", {"quantity": 1, "reason_code": "damage", "reason": "Crushed pallet"}),
        ("post", "/recalls", {"title": "Recall", "reason": "Supplier alert", "batch_ids": [bid]}),
        ("put", "/batch-policy", {"warn_days": [30]}),
        ("get", "/fleet/vehicles", None), ("get", "/dashboard", None), ("get", "/promotions", None), ("get", "/forecast", None),
        ("get", "/quality/inspections", None), ("get", "/reports/centre", None), ("get", "/merch/must-stock", None), ("get", "/shipments", None),
    ):
        r = await getattr(ac, method)(f"{API}{path}", headers=sk, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (path, r.status_code)


@pytest.mark.asyncio
async def test_quality_officer_inspects_and_holds_but_cannot_write_off_or_recall(client, seeded, db_session):
    ac, seed = client
    await _admin(ac, seed, db_session)
    pid, bid = await _batch(db_session, seed)
    qc = await _staff(ac, db_session, seed, "fmcg_quality")
    ins = await ac.post(f"{API}/quality/inspections", headers=qc, json={"product_id": pid, "batch_id": bid, "hold_until_decided": True})
    assert ins.status_code == 200, ins.text
    assert (await ac.post(f"{API}/quality/inspections/{ins.json()['data']['id']}/decide", headers=qc, json={"result": "fail", "note": "Wrong label"})).status_code == 200
    assert (await ac.get(f"{API}/batches?status=held", headers=qc)).json()["data"]["counts"]["held"] == 1
    assert (await ac.post(f"{API}/batches/{bid}/release", headers=qc)).status_code == 200
    assert (await ac.post(f"{API}/batches/{bid}/hold", headers=qc, json={"reason": "Second look needed"})).status_code == 200
    assert (await ac.post(f"{API}/complaints", headers=qc, json={"category": "other", "description": "Late delivery reported"})).status_code == 200
    for method, path, body in (
        ("post", f"/batches/{bid}/write-off", {"quantity": 1, "reason_code": "damage", "reason": "Crushed pallet"}),
        ("post", "/recalls", {"title": "Recall", "reason": "Supplier alert", "batch_ids": [bid]}),
        ("get", "/warehouse/report", None), ("get", "/fleet/vehicles", None), ("get", "/dashboard", None), ("get", "/promotions", None),
        ("get", "/shipments", None), ("get", "/reports/centre", None),
    ):
        r = await getattr(ac, method)(f"{API}{path}", headers=qc, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (path, r.status_code)


@pytest.mark.asyncio
async def test_fleet_manager_runs_vehicles_and_assigns_them(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    fm = await _staff(ac, db_session, seed, "fmcg_fleet")
    v = await ac.post(f"{API}/fleet/vehicles", headers=fm, json={"plate": "GR 88-26", "name": "Truck 1"})
    assert v.status_code == 200, v.text
    route = (await ac.post(f"{API}/routes", headers=h, json={"code": f"R{uuid4().hex[:4]}", "name": "North"})).json()["data"]
    dispatch = (await ac.post(f"{API}/dispatches", headers=h, json={"route_id": route["id"]})).json()["data"]["id"]
    assert (await ac.post(f"{API}/dispatches/{dispatch}/vehicle", headers=fm, json={"vehicle_id": v.json()["data"]["id"]})).status_code == 200
    assert (await ac.get(f"{API}/fleet/report?start=2026-01-01&end=2026-02-01", headers=fm)).status_code == 200
    # A fleet manager cannot open or settle a dispatch, or reach other desks' screens.
    assert (await ac.post(f"{API}/dispatches", headers=fm, json={"route_id": route["id"]})).status_code == 403
    assert (await ac.post(f"{API}/dispatches/{dispatch}/settle", headers=fm, json={"counted_cash": 0})).status_code == 403
    for path in ("/batches", "/warehouse/report", "/quality/inspections", "/dashboard", "/promotions", "/forecast", "/shipments"):
        assert (await ac.get(f"{API}{path}", headers=fm)).status_code == 403, path


@pytest.mark.asyncio
async def test_new_roles_can_only_be_given_in_fmcg_companies(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    for role in ROLES:
        r = await ac.post("/api/v1/users", headers=h, json={"email": f"{role}-new@alpha.example.com", "full_name": f"New {role}", "password": "SecurePass123!", "role": role})
        assert r.status_code == 200, (role, r.text)
    await set_tenant_industry(db_session, seed["t1"], "retail")
    for role in ROLES:
        r = await ac.post("/api/v1/users", headers=h, json={"email": f"{role}-retail@alpha.example.com", "full_name": f"Retail {role}", "password": "SecurePass123!", "role": role})
        assert r.status_code >= 400, role
