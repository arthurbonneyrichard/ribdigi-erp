"""Gym facilities: sauna, pool, studio bookings."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from uuid import uuid4

import pytest

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _member, _open, _plan, _sell
from tests.test_gym_stage1 import _active

P = "/api/v1/public/gym-member"


def _at(hour, minute=0, days=1):
    day = date.today() + timedelta(days=days)
    return datetime.combine(day, time(hour, minute)).isoformat()


async def _facility(ac, h, **extra):
    body = {"name": f"Sauna {uuid4().hex[:4]}", "kind": "sauna", "capacity": 2, "open_time": "06:00", "close_time": "22:00", "max_minutes": 60}
    body.update(extra)
    r = await ac.post("/api/v1/gym/facilities", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_capacity_hours_overlap_and_membership_rules(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    fac = await _facility(ac, h)
    a, b, c = await _active(ac, h), await _active(ac, h), await _active(ac, h)
    url = f"/api/v1/gym/facilities/{fac['id']}/book"
    ok = await ac.post(url, headers=h, json={"member_id": a["id"], "starts_at": _at(10), "minutes": 60})
    assert ok.status_code == 200, ok.text
    assert (await ac.post(url, headers=h, json={"member_id": a["id"], "starts_at": _at(10, 30), "minutes": 30})).status_code == 409  # own overlap
    assert (await ac.post(url, headers=h, json={"member_id": b["id"], "starts_at": _at(10, 30), "minutes": 30})).status_code == 200
    full = await ac.post(url, headers=h, json={"member_id": c["id"], "starts_at": _at(10, 45), "minutes": 15})
    assert full.status_code == 409 and "full" in full.json()["detail"]
    assert (await ac.post(url, headers=h, json={"member_id": c["id"], "starts_at": _at(11), "minutes": 60})).status_code == 200  # slot after is free
    assert (await ac.post(url, headers=h, json={"member_id": c["id"], "starts_at": _at(5, 30), "minutes": 30})).status_code == 409  # before opening
    assert (await ac.post(url, headers=h, json={"member_id": c["id"], "starts_at": _at(21, 30), "minutes": 60})).status_code == 409  # past closing
    assert (await ac.post(url, headers=h, json={"member_id": c["id"], "starts_at": _at(15), "minutes": 90})).status_code == 422  # over max
    assert (await ac.post(url, headers=h, json={"member_id": c["id"], "starts_at": _at(10, days=-3), "minutes": 30})).status_code == 422
    nobody = await _member(ac, h)
    assert (await ac.post(url, headers=h, json={"member_id": nobody["id"], "starts_at": _at(16), "minutes": 30})).status_code == 409
    rows = (await ac.get(f"/api/v1/gym/facility-bookings?day={(date.today() + timedelta(days=1)).isoformat()}", headers=h)).json()["data"]
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_cancelling_frees_the_place_and_a_closed_facility_takes_no_bookings(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    fac = await _facility(ac, h, capacity=1)
    a, b = await _active(ac, h), await _active(ac, h)
    url = f"/api/v1/gym/facilities/{fac['id']}/book"
    first = (await ac.post(url, headers=h, json={"member_id": a["id"], "starts_at": _at(9), "minutes": 30})).json()["data"]
    assert (await ac.post(url, headers=h, json={"member_id": b["id"], "starts_at": _at(9), "minutes": 30})).status_code == 409
    assert (await ac.post(f"/api/v1/gym/facility-bookings/{first['id']}", headers=h, json={"status": "cancelled"})).status_code == 200
    assert (await ac.post(f"/api/v1/gym/facility-bookings/{first['id']}", headers=h, json={"status": "attended"})).status_code == 409
    assert (await ac.post(url, headers=h, json={"member_id": b["id"], "starts_at": _at(9), "minutes": 30})).status_code == 200
    await ac.post(f"/api/v1/gym/facilities/{fac['id']}/active", headers=h, json={"is_active": False})
    assert (await ac.post(url, headers=h, json={"member_id": a["id"], "starts_at": _at(13), "minutes": 30})).status_code == 409
    bad = await ac.post("/api/v1/gym/facilities", headers=h, json={"name": "Bad hours", "open_time": "22:00", "close_time": "06:00"})
    assert bad.status_code == 422
    assert (await ac.post("/api/v1/gym/facilities", headers=h, json={"name": fac["name"]})).status_code == 409


@pytest.mark.asyncio
async def test_member_portal_books_their_own_and_cannot_cancel_anothers(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    fac = await _facility(ac, h)
    a, b = await _active(ac, h), await _active(ac, h)
    ta = (await ac.post(f"/api/v1/gym/members/{a['id']}/portal-link", headers=h, json={})).json()["data"]["token"]
    tb = (await ac.post(f"/api/v1/gym/members/{b['id']}/portal-link", headers=h, json={})).json()["data"]["token"]
    assert [f["id"] for f in (await ac.get(f"{P}/facilities", headers={"X-Portal-Token": ta})).json()["data"]] == [fac["id"]]
    r = await ac.post(f"{P}/facilities/{fac['id']}/book", headers={"X-Portal-Token": ta}, json={"starts_at": _at(12), "minutes": 30})
    assert r.status_code == 200 and r.json()["data"]["member_id"] == a["id"]
    assert (await ac.post(f"{P}/facilities/{fac['id']}/book", headers={"X-Portal-Token": ta}, json={"member_id": b["id"], "starts_at": _at(14), "minutes": 30})).status_code == 422
    bid = r.json()["data"]["id"]
    assert (await ac.post(f"{P}/facility-bookings/{bid}/cancel", headers={"X-Portal-Token": tb})).status_code == 404
    assert (await ac.get(f"{P}/facility-bookings", headers={"X-Portal-Token": tb})).json()["data"] == []
    assert (await ac.post(f"{P}/facility-bookings/{bid}/cancel", headers={"X-Portal-Token": ta})).status_code == 200


@pytest.mark.asyncio
async def test_facilities_are_tenant_scoped_and_gym_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    theirs = m.GymFacility(tenant_id=seed["t2"].id, name="Theirs", kind="pool")
    db_session.add(theirs)
    await db_session.commit()
    await _open(ac, h)
    member = await _active(ac, h)
    assert (await ac.post(f"/api/v1/gym/facilities/{theirs.id}/book", headers=h, json={"member_id": member["id"], "starts_at": _at(10), "minutes": 30})).status_code == 404
    assert (await ac.post(f"/api/v1/gym/facilities/{theirs.id}/active", headers=h, json={"is_active": False})).status_code == 404
    assert (await ac.get("/api/v1/gym/facilities", headers=h)).json()["data"] == []
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/gym/facilities", headers=h)).status_code == 403
