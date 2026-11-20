"""Gym door: credentials, scanning, devices and safe offline sync."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _member, _open, _plan, _sell


async def _issue(ac, h, member, **extra):
    r = await ac.post("/api/v1/gym/credentials", headers=h, json={"member_id": member["id"], **extra})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _ev(token, ago_minutes=5, event_id=None):
    when = (datetime.now(timezone.utc) - timedelta(minutes=ago_minutes)).isoformat()
    return {"event_id": event_id or uuid4().hex, "token": token, "occurred_at": when}


@pytest.mark.asyncio
async def test_token_is_shown_once_stored_hashed_and_scans_the_member_in(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    cred = await _issue(ac, h, member)
    assert cred["token"].startswith("gym_") and cred["qr_png"].startswith("data:image/png;base64,")
    row = (await db_session.execute(select(m.GymCredential))).scalars().first()
    assert row.token_hash != cred["token"] and cred["token"] not in str(row.__dict__)
    assert "token" not in (await ac.get(f"/api/v1/gym/members/{member['id']}/credentials", headers=h)).json()["data"][0]
    ok = (await ac.post("/api/v1/gym/check-ins/scan", headers=h, json={"token": cred["token"]})).json()["data"]
    assert ok["allowed"] is True
    unknown = (await ac.post("/api/v1/gym/check-ins/scan", headers=h, json={"token": "gym_not_a_real_code"})).json()["data"]
    assert unknown["allowed"] is False and "not recognised" in unknown["message"]
    assert (await ac.post(f"/api/v1/gym/credentials/{cred['id']}/revoke", headers=h)).status_code == 200
    assert (await ac.post(f"/api/v1/gym/credentials/{cred['id']}/revoke", headers=h)).status_code == 409
    gone = (await ac.post("/api/v1/gym/check-ins/scan", headers=h, json={"token": cred["token"]})).json()["data"]
    assert gone["allowed"] is False and "cancelled" in gone["message"]


@pytest.mark.asyncio
async def test_a_card_number_can_only_belong_to_one_member(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, b = await _member(ac, h), await _member(ac, h)
    await _issue(ac, h, a, kind="rfid", token="04A1B2C3D4")
    dup = await ac.post("/api/v1/gym/credentials", headers=h, json={"member_id": b["id"], "kind": "rfid", "token": "04A1B2C3D4"})
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_offline_sync_is_idempotent_and_does_not_trust_old_or_unknown_scans(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    plan, member, lapsed = await _plan(ac, h), await _member(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    good, expired = await _issue(ac, h, member), await _issue(ac, h, lapsed)
    dev = (await ac.post("/api/v1/gym/devices", headers=h, json={"name": "Front reader", "kind": "qr_scanner"})).json()["data"]
    assert dev["verified"] is False and "not yet tested" in dev["status"]
    first = _ev(good["token"])
    batch = {"device_id": dev["id"], "events": [first, _ev(expired["token"]), _ev("gym_unknown_code_here"), _ev(good["token"], ago_minutes=60 * 30)]}
    r = await ac.post("/api/v1/gym/door/sync", headers=h, json=batch)
    assert r.status_code == 200, r.text
    outs = [x["outcome"] for x in r.json()["data"]["results"]]
    assert sorted(outs) == ["allowed", "refused", "too_old", "unknown"]
    assert r.json()["data"]["accepted"] == 1
    again = await ac.post("/api/v1/gym/door/sync", headers=h, json={"device_id": dev["id"], "events": [first]})
    assert again.json()["data"]["results"][0]["duplicate"] is True and again.json()["data"]["accepted"] == 0
    visits = (await db_session.execute(select(m.GymCheckIn).where(m.GymCheckIn.allowed.is_(True)))).scalars().all()
    assert len(visits) == 1
    flagged = (await ac.get("/api/v1/gym/door/attention", headers=h)).json()["data"]
    assert len(flagged) == 3
    assert (await ac.post(f"/api/v1/gym/door/attention/{flagged[0]['id']}/reviewed", headers=h)).status_code == 200
    assert len((await ac.get("/api/v1/gym/door/attention", headers=h)).json()["data"]) == 2
    future = _ev(good["token"], ago_minutes=-120)
    f = (await ac.post("/api/v1/gym/door/sync", headers=h, json={"events": [future]})).json()["data"]["results"][0]
    assert f["outcome"] == "refused"


@pytest.mark.asyncio
async def test_roster_lists_only_active_members_and_never_raw_tokens(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    plan, member, lapsed = await _plan(ac, h), await _member(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    good = await _issue(ac, h, member)
    await _issue(ac, h, lapsed)
    data = (await ac.get("/api/v1/gym/door/roster", headers=h)).json()["data"]
    assert len(data["entries"]) == 1 and data["entries"][0]["member_id"] == member["id"]
    assert good["token"] not in str(data)


@pytest.mark.asyncio
async def test_door_is_tenant_scoped_and_gym_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    other = m.GymMember(tenant_id=seed["t2"].id, member_number="GM-1", full_name="Theirs", joined_on=datetime.now().date())
    db_session.add(other)
    await db_session.commit()
    cred = m.GymCredential(tenant_id=seed["t2"].id, member_id=other.id, kind="qr", token_hash="a" * 64)
    dev = m.GymDevice(tenant_id=seed["t2"].id, name="Theirs")
    db_session.add_all([cred, dev])
    await db_session.commit()
    assert (await ac.post("/api/v1/gym/credentials", headers=h, json={"member_id": other.id})).status_code == 404
    assert (await ac.post(f"/api/v1/gym/credentials/{cred.id}/revoke", headers=h)).status_code == 404
    assert (await ac.post(f"/api/v1/gym/devices/{dev.id}/verified", headers=h, json={"verified": True})).status_code == 404
    assert (await ac.post("/api/v1/gym/door/sync", headers=h, json={"device_id": dev.id, "events": [_ev("gym_whatever")]})).status_code == 404
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/gym/devices", headers=h)).status_code == 403
