"""Gym stage 1: waiting list, trainers and sessions, lockers, equipment, guests."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _member, _open, _plan, _sell


async def _active(ac, h):
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    return member


async def _trainer(ac, h, name=None):
    r = await ac.post("/api/v1/gym/trainers", headers=h, json={"full_name": name or f"Kojo {uuid4().hex[:5]}", "session_price": 80})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _soon(hours=2):
    return (datetime.utcnow() + timedelta(hours=hours)).replace(microsecond=0).isoformat()


@pytest.mark.asyncio
async def test_waiting_list_promotes_in_order_when_a_place_frees(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    a, b, c = await _active(ac, h), await _active(ac, h), await _active(ac, h)
    cls = (await ac.post("/api/v1/gym/classes", headers=h, json={"name": "Yoga", "starts_at": _soon(), "capacity": 1})).json()["data"]
    assert (await ac.post(f"/api/v1/gym/classes/{cls['id']}/book", headers=h, json={"member_id": a["id"]})).status_code == 200
    full = await ac.post(f"/api/v1/gym/classes/{cls['id']}/book", headers=h, json={"member_id": b["id"]})
    assert full.status_code == 409
    w1 = await ac.post(f"/api/v1/gym/classes/{cls['id']}/book", headers=h, json={"member_id": b["id"], "waitlist": True})
    assert w1.json()["data"]["waiting"] == 1 and w1.json()["data"]["booked"] == 1
    await ac.post(f"/api/v1/gym/classes/{cls['id']}/book", headers=h, json={"member_id": c["id"], "waitlist": True})
    dup = await ac.post(f"/api/v1/gym/classes/{cls['id']}/book", headers=h, json={"member_id": b["id"], "waitlist": True})
    assert dup.status_code == 409
    booking = w1.json()["data"]
    first = next(x for x in (await ac.get("/api/v1/gym/classes", headers=h)).json()["data"] if x["id"] == cls["id"])["bookings"][0]
    done = await ac.post(f"/api/v1/gym/bookings/{first['id']}", headers=h, json={"status": "cancelled"})
    data = done.json()["data"]
    assert data["booked"] == 1 and data["waiting"] == 1
    assert data["bookings"][0]["member_id"] == b["id"]
    assert data["waitlist"][0]["member_id"] == c["id"]
    assert booking["capacity"] == 1


@pytest.mark.asyncio
async def test_a_trainer_cannot_be_double_booked(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    a, b = await _active(ac, h), await _active(ac, h)
    t = await _trainer(ac, h)
    body = {"trainer_id": t["id"], "member_id": a["id"], "starts_at": _soon(3), "minutes": 60}
    first = await ac.post("/api/v1/gym/training-sessions", headers=h, json=body)
    assert first.status_code == 200, first.text
    clash = await ac.post("/api/v1/gym/training-sessions", headers=h, json={**body, "member_id": b["id"], "minutes": 30})
    assert clash.status_code == 409
    later = await ac.post("/api/v1/gym/training-sessions", headers=h, json={**body, "member_id": b["id"], "starts_at": _soon(5)})
    assert later.status_code == 200
    sid = first.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/gym/training-sessions/{sid}", headers=h, json={"status": "cancelled"})).status_code == 200
    assert (await ac.post(f"/api/v1/gym/training-sessions/{sid}", headers=h, json={"status": "completed"})).status_code == 409
    again = await ac.post("/api/v1/gym/training-sessions", headers=h, json={**body, "member_id": b["id"]})
    assert again.status_code == 200
    dup = await ac.post("/api/v1/gym/trainers", headers=h, json={"full_name": t["full_name"]})
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_a_session_needs_an_active_member_and_a_future_time(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    t = await _trainer(ac, h)
    nobody = await _member(ac, h)
    r = await ac.post("/api/v1/gym/training-sessions", headers=h, json={"trainer_id": t["id"], "member_id": nobody["id"], "starts_at": _soon()})
    assert r.status_code == 409
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    r = await ac.post("/api/v1/gym/training-sessions", headers=h, json={"trainer_id": t["id"], "member_id": nobody["id"], "starts_at": past})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_lockers_one_per_member_and_release(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    a, b = await _active(ac, h), await _active(ac, h)
    l1 = (await ac.post("/api/v1/gym/lockers", headers=h, json={"number": "L1"})).json()["data"]
    l2 = (await ac.post("/api/v1/gym/lockers", headers=h, json={"number": "L2"})).json()["data"]
    assert (await ac.post("/api/v1/gym/lockers", headers=h, json={"number": "L1"})).status_code == 409
    assert (await ac.post(f"/api/v1/gym/lockers/{l1['id']}/assign", headers=h, json={"member_id": a["id"]})).status_code == 200
    assert (await ac.post(f"/api/v1/gym/lockers/{l1['id']}/assign", headers=h, json={"member_id": b["id"]})).status_code == 409
    assert (await ac.post(f"/api/v1/gym/lockers/{l2['id']}/assign", headers=h, json={"member_id": a["id"]})).status_code == 409
    assert (await ac.post(f"/api/v1/gym/lockers/{l1['id']}/release", headers=h)).status_code == 200
    assert (await ac.post(f"/api/v1/gym/lockers/{l1['id']}/release", headers=h)).status_code == 409
    assert (await ac.post(f"/api/v1/gym/lockers/{l1['id']}/assign", headers=h, json={"member_id": b["id"]})).status_code == 200
    nobody = await _member(ac, h)
    assert (await ac.post(f"/api/v1/gym/lockers/{l2['id']}/assign", headers=h, json={"member_id": nobody["id"]})).status_code == 409


@pytest.mark.asyncio
async def test_equipment_fault_to_repair_cycle(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    eq = (await ac.post("/api/v1/gym/equipment", headers=h, json={"name": "Treadmill 1", "category": "Cardio"})).json()["data"]
    assert eq["status"] == "available"
    f1 = (await ac.post(f"/api/v1/gym/equipment/{eq['id']}/faults", headers=h, json={"fault": "Belt slips"})).json()["data"]
    f2 = (await ac.post(f"/api/v1/gym/equipment/{eq['id']}/faults", headers=h, json={"fault": "Console dead"})).json()["data"]
    row = (await ac.get("/api/v1/gym/equipment", headers=h)).json()["data"][0]
    assert row["status"] == "maintenance" and row["open_faults"] == 2
    done = (await ac.post(f"/api/v1/gym/maintenance/{f1['id']}/close", headers=h, json={"resolution": "Belt replaced"})).json()["data"]
    assert done["equipment_status"] == "maintenance"
    done = (await ac.post(f"/api/v1/gym/maintenance/{f2['id']}/close", headers=h, json={"resolution": "Console swapped"})).json()["data"]
    assert done["equipment_status"] == "available"
    assert (await ac.post(f"/api/v1/gym/maintenance/{f2['id']}/close", headers=h, json={"resolution": "Again please"})).status_code == 409
    f3 = (await ac.post(f"/api/v1/gym/equipment/{eq['id']}/faults", headers=h, json={"fault": "Frame cracked"})).json()["data"]
    gone = (await ac.post(f"/api/v1/gym/maintenance/{f3['id']}/close", headers=h, json={"resolution": "Beyond repair", "retire": True})).json()["data"]
    assert gone["equipment_status"] == "retired"
    assert (await ac.post(f"/api/v1/gym/equipment/{eq['id']}/faults", headers=h, json={"fault": "Still broken"})).status_code == 409


@pytest.mark.asyncio
async def test_guests_in_and_out(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    host = await _active(ac, h)
    g = await ac.post("/api/v1/gym/guests", headers=h, json={"guest_name": "Yaw Mensah", "host_member_id": host["id"]})
    assert g.status_code == 200, g.text
    assert (await ac.post("/api/v1/gym/guests", headers=h, json={"guest_name": "yaw mensah"})).status_code == 409
    gid = g.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/gym/guests/{gid}/out", headers=h)).status_code == 200
    assert (await ac.post(f"/api/v1/gym/guests/{gid}/out", headers=h)).status_code == 409
    lapsed = await _member(ac, h)
    assert (await ac.post("/api/v1/gym/guests", headers=h, json={"guest_name": "Efua", "host_member_id": lapsed["id"]})).status_code == 409
    assert len((await ac.get("/api/v1/gym/guests", headers=h)).json()["data"]) == 1


@pytest.mark.asyncio
async def test_stage1_is_tenant_scoped_and_gym_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    theirs = m.GymLocker(tenant_id=seed["t2"].id, number="X1", status="free")
    their_eq = m.GymEquipment(tenant_id=seed["t2"].id, name="Theirs", status="available")
    db_session.add_all([theirs, their_eq])
    await db_session.commit()
    mine = await _member(ac, h)
    assert (await ac.post(f"/api/v1/gym/lockers/{theirs.id}/assign", headers=h, json={"member_id": mine["id"]})).status_code == 404
    assert (await ac.post(f"/api/v1/gym/equipment/{their_eq.id}/faults", headers=h, json={"fault": "Broken thing"})).status_code == 404
    assert len((await ac.get("/api/v1/gym/lockers", headers=h)).json()["data"]) == 0
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    for path in ("lockers", "equipment", "guests", "trainers", "training-sessions"):
        assert (await ac.get(f"/api/v1/gym/{path}", headers=h)).status_code == 403
