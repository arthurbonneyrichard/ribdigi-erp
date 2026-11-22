"""RFID card attendance with simulated reader traffic (no real hardware)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_people import _user

pytestmark = pytest.mark.asyncio
B = "/api/v1/hrm/rfid"


async def _reader(ac, h, name="Front door"):
    r = await ac.post(f"{B}/readers", headers=h, json={"name": name})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def test_cards_and_taps(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h)
    q = await _person(ac, h)
    reader = await _reader(ac, h)
    token = reader["token"]
    assert token.startswith("rfid_")
    # the token is shown once, never listed, and only its hash is stored
    assert "token" not in (await ac.get(f"{B}/readers", headers=h)).json()["data"][0]
    stored = (await db_session.execute(select(m.HrmRfidReader))).scalars().one()
    assert token not in stored.token_hash and len(stored.token_hash) == 64

    assert (await ac.post(f"{B}/cards", headers=h, json={"employee_id": p["id"], "card_uid": "ab:12 cd:34"})).status_code == 200
    # same card cannot go to someone else; a bad number is refused
    assert (await ac.post(f"{B}/cards", headers=h, json={"employee_id": q["id"], "card_uid": "AB12CD34"})).status_code == 409
    assert (await ac.post(f"{B}/cards", headers=h, json={"employee_id": q["id"], "card_uid": "!!!!!"})).status_code == 422

    hdr = {"X-Reader-Token": token}
    t0 = datetime.utcnow() - timedelta(hours=2)
    first = await ac.post(f"{B}/punch", headers=hdr, json={"card_uid": "AB12CD34", "ref": "t1", "at": t0.isoformat()})
    assert first.json()["data"] == {"result": "stored", "kind": "in", "name": p["full_name"]}
    second = await ac.post(f"{B}/punch", headers=hdr, json={"card_uid": "AB12CD34", "ref": "t2", "at": (t0 + timedelta(hours=1)).isoformat()})
    assert second.json()["data"]["kind"] == "out"
    # the same tap sent twice is stored once
    assert (await ac.post(f"{B}/punch", headers=hdr, json={"card_uid": "AB12CD34", "ref": "t2", "at": (t0 + timedelta(hours=1)).isoformat()})).json()["data"]["result"] == "duplicate"
    assert (await ac.post(f"{B}/punch", headers=hdr, json={"card_uid": "FFFF0000", "ref": "t3"})).json()["data"]["result"] == "unknown_card"
    events = (await db_session.execute(select(m.HrmClockEvent).where(m.HrmClockEvent.source == "rfid"))).scalars().all()
    assert sorted(e.kind for e in events) == ["in", "out"]

    # a new card replaces the old one
    assert (await ac.post(f"{B}/cards", headers=h, json={"employee_id": p["id"], "card_uid": "99998888"})).status_code == 200
    assert (await ac.post(f"{B}/punch", headers=hdr, json={"card_uid": "AB12CD34", "ref": "t4"})).json()["data"]["result"] == "unknown_card"


async def test_reader_security(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h, email="rf@alpha.example.com")
    token = (await _reader(ac, h))["token"]
    await ac.post(f"{B}/cards", headers=h, json={"employee_id": p["id"], "card_uid": "AAAA1111"})
    body = {"card_uid": "AAAA1111", "ref": "x1"}
    assert (await ac.post(f"{B}/punch", json=body)).status_code == 401
    assert (await ac.post(f"{B}/punch", headers={"X-Reader-Token": "rfid_nope"}, json=body)).status_code == 401
    assert (await ac.post(f"{B}/punch", headers={"X-Reader-Token": token}, json={**body, "at": (datetime.utcnow() + timedelta(days=1)).isoformat()})).status_code == 422
    assert (await ac.post(f"{B}/punch", headers={"X-Reader-Token": token}, json={**body, "at": (datetime.utcnow() - timedelta(days=30)).isoformat()})).status_code == 422
    # staff and officers cannot register readers
    staff = await _user(ac, h, "rf@alpha.example.com", "hrm_employee")
    officer = await _user(ac, h, "offr@alpha.example.com", "hrm_officer")
    assert (await ac.post(f"{B}/readers", headers=staff, json={"name": "Mine"})).status_code == 403
    assert (await ac.post(f"{B}/readers", headers=officer, json={"name": "Mine"})).status_code == 403
    # switched off, the token stops working
    rid = (await ac.get(f"{B}/readers", headers=h)).json()["data"][0]["id"]
    assert (await ac.post(f"{B}/readers/{rid}/off", headers=h)).status_code == 200
    assert (await ac.post(f"{B}/punch", headers={"X-Reader-Token": token}, json=body)).status_code == 401
