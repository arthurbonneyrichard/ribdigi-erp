"""Gym: recurring classes, per-plan door rules, branches."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app import gym_access
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _door, _member, _open, _plan, _sell
from tests.test_gym_stage1 import _soon


@pytest.mark.asyncio
async def test_a_class_repeats_weekly_and_the_whole_series_can_be_cancelled(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    r = await ac.post("/api/v1/gym/classes", headers=h, json={"name": "Spin", "starts_at": _soon(24), "capacity": 10, "repeat_weeks": 4})
    assert r.status_code == 200, r.text
    rows = [c for c in (await ac.get("/api/v1/gym/classes", headers=h)).json()["data"] if c["name"] == "Spin"]
    assert len(rows) == 4
    gap = datetime.fromisoformat(rows[1]["starts_at"]) - datetime.fromisoformat(rows[0]["starts_at"])
    assert gap == timedelta(weeks=1)
    assert (await ac.post("/api/v1/gym/classes", headers=h, json={"name": "X", "starts_at": _soon(), "capacity": 5, "repeat_weeks": 80})).status_code == 422
    second = rows[1]["id"]
    assert (await ac.post(f"/api/v1/gym/classes/{second}/cancel?series=true", headers=h)).status_code == 200
    left = [c for c in (await ac.get("/api/v1/gym/classes", headers=h)).json()["data"] if c["name"] == "Spin"]
    assert len(left) == 1  # only the first, before the cancelled point, remains


def test_window_logic_handles_midnight():
    assert gym_access._in_window("06:00", "22:00", "07:30")
    assert not gym_access._in_window("06:00", "22:00", "22:00")
    assert gym_access._in_window("22:00", "02:00", "23:30") and gym_access._in_window("22:00", "02:00", "01:00")
    assert not gym_access._in_window("22:00", "02:00", "12:00")


@pytest.mark.asyncio
async def test_plan_rules_are_validated_and_enforced_at_the_door(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    url = f"/api/v1/gym/plans/{plan['id']}/access"
    assert (await ac.post(url, headers=h, json={"access_start": "06:00"})).status_code == 422
    assert (await ac.post(url, headers=h, json={"access_start": "6am", "access_end": "10pm"})).status_code == 422
    assert (await ac.post(url, headers=h, json={"access_days": [9]})).status_code == 422
    # A window that excludes right now (local time is Africa/Accra = UTC).
    now = datetime.now(timezone.utc)
    start = (now + timedelta(hours=2)).strftime("%H:%M")
    end = (now + timedelta(hours=3)).strftime("%H:%M")
    ok = await ac.post(url, headers=h, json={"access_start": start, "access_end": end})
    assert ok.status_code == 200, ok.text
    refused = await _door(ac, h, member)
    assert refused["allowed"] is False and "for" in refused["message"]
    # Open all day on every day: let in.
    await ac.post(url, headers=h, json={})
    assert (await _door(ac, h, member))["allowed"] is True
    plans = (await ac.get("/api/v1/gym/plans", headers=h)).json()["data"]
    assert plans[0]["access_start"] is None and plans[0]["branch_scope"] == "all"


@pytest.mark.asyncio
async def test_a_day_the_plan_does_not_cover_is_refused(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    other_day = (datetime.now(timezone.utc).isoweekday() % 7) + 1
    assert (await ac.post(f"/api/v1/gym/plans/{plan['id']}/access", headers=h, json={"access_days": [other_day]})).status_code == 200
    out = await _door(ac, h, member)
    assert out["allowed"] is False and "does not cover" in out["message"]


@pytest.mark.asyncio
async def test_branches_home_scope_and_report(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    a = (await ac.post("/api/v1/gym/branches", headers=h, json={"code": "acc", "name": "Accra Central"})).json()["data"]
    b = (await ac.post("/api/v1/gym/branches", headers=h, json={"code": "KSI", "name": "Kumasi"})).json()["data"]
    assert (await ac.post("/api/v1/gym/branches", headers=h, json={"code": "ACC", "name": "Dup"})).status_code == 409
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    assert (await ac.post(f"/api/v1/gym/members/{member['id']}/branch", headers=h, json={"branch_id": a["id"]})).status_code == 200
    assert (await ac.post(f"/api/v1/gym/plans/{plan['id']}/access", headers=h, json={"branch_scope": "home"})).status_code == 200
    elsewhere = await ac.post("/api/v1/gym/check-ins", headers=h, json={"member_id": member["id"], "branch_id": b["id"]})
    assert elsewhere.json()["data"]["allowed"] is False and "home branch" in elsewhere.json()["data"]["message"]
    home = await ac.post("/api/v1/gym/check-ins", headers=h, json={"member_id": member["id"], "branch_id": a["id"]})
    assert home.json()["data"]["allowed"] is True
    await ac.post(f"/api/v1/gym/branches/{b['id']}/active", headers=h, json={"is_active": False})
    closed = await ac.post("/api/v1/gym/check-ins", headers=h, json={"member_id": member["id"], "branch_id": b["id"]})
    assert closed.status_code == 409
    rep = (await ac.get("/api/v1/gym/reports/branches", headers=h)).json()["data"]
    mine = next(r for r in rep if r["branch_id"] == a["id"])
    assert mine["visits"] == 1 and mine["home_members"] == 1


@pytest.mark.asyncio
async def test_branches_are_tenant_scoped(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    theirs = m.GymBranch(tenant_id=seed["t2"].id, code="X", name="Theirs")
    db_session.add(theirs)
    await db_session.commit()
    member = await _member(ac, h)
    assert (await ac.post(f"/api/v1/gym/members/{member['id']}/branch", headers=h, json={"branch_id": theirs.id})).status_code == 404
    assert (await ac.post(f"/api/v1/gym/branches/{theirs.id}/active", headers=h, json={"is_active": False})).status_code == 404
    assert (await ac.get("/api/v1/gym/branches", headers=h)).json()["data"] == []
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/gym/branches", headers=h)).status_code == 403
