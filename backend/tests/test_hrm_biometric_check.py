"""ZKTeco setup check: terminal heard or not, BioTime sign-in and read (simulated), PIN mismatches."""

from __future__ import annotations

import httpx
import pytest

from app import hrm_biometric
from tests.test_hrm_desk import _admin, _person

pytestmark = pytest.mark.asyncio


async def test_terminal_check_and_unknown_pins(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h, full_name="Has Pin", biometric_id="1007")
    await _person(ac, h, full_name="No Pin")
    link = (await ac.post("/api/v1/hrm/biometric", headers=h, json={"kind": "device", "name": "Front door", "device_serial": "CQZ7232060123"})).json()["data"]
    first = (await ac.post(f"/api/v1/hrm/biometric/{link['id']}/check", headers=h)).json()["data"]
    assert first["status"] == "never" and any("CQZ7232060123" in s for s in first["steps"])
    assert first["staff_without_terminal_id"] == ["No Pin"]

    await ac.get("/iclock/cdata?SN=CQZ7232060123&options=all")
    await ac.post("/iclock/cdata?SN=CQZ7232060123&table=ATTLOG", content="9999\t2026-10-05 08:00:00\t0\t1\n9999\t2026-10-05 17:00:00\t1\t1\n")
    after = (await ac.post(f"/api/v1/hrm/biometric/{link['id']}/check", headers=h)).json()["data"]
    assert after["status"] == "ok"
    assert after["unknown_pins"][0]["pin"] == "9999" and after["unknown_pins"][0]["count"] == 2


async def test_biotime_check_does_not_store(client, db_session, monkeypatch):
    ac, seed = client
    h = await _admin(ac, seed, db_session)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/jwt-api-token-auth/":
            return httpx.Response(200, json={"token": "abc"})
        if request.url.path == "/iclock/api/transactions/":
            return httpx.Response(200, json={"count": 321, "next": None, "data": [{"id": 1, "emp_code": "55", "punch_time": "2026-11-02 08:01:00", "punch_state": "0"}]})
        return httpx.Response(404)

    monkeypatch.setattr(hrm_biometric, "transport", httpx.MockTransport(handler))
    link = (await ac.post("/api/v1/hrm/biometric", headers=h, json={"kind": "biotime", "name": "BioTime", "base_url": "https://biotime.example.com", "username": "api", "password": "s3cret"})).json()["data"]
    out = (await ac.post(f"/api/v1/hrm/biometric/{link['id']}/check", headers=h)).json()["data"]
    assert out["status"] == "ok" and out["punches_on_server"] == 321
    listed = (await ac.get("/api/v1/hrm/biometric", headers=h)).json()["data"][0]
    assert listed["last_synced_at"] == link["last_synced_at"]  # a check is not a sync

    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"non_field_errors": ["Unable to log in"]})

    monkeypatch.setattr(hrm_biometric, "transport", httpx.MockTransport(refuse))
    out = (await ac.post(f"/api/v1/hrm/biometric/{link['id']}/check", headers=h)).json()["data"]
    assert out["status"] == "sign_in_refused"
