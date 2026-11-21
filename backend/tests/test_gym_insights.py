"""Gym insights: rule-based churn risk, attendance, equipment, summary, workout drafts, off switch."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _door, _member, _open, _plan, _sell
from tests.test_gym_fitness import _exercise

U = "/api/v1/gym/insights"


@pytest.mark.asyncio
async def test_churn_risk_ranks_members_with_reasons_and_says_it_is_rules(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    plan = await _plan(ac, h, days=10)
    quiet, busy = await _member(ac, h), await _member(ac, h)
    for mem in (quiet, busy):
        await _sell(ac, h, mem, plan)
        row = await db_session.get(m.GymMember, mem["id"])
        row.joined_on = date.today() - timedelta(days=40)
    await db_session.commit()
    await _door(ac, h, busy)
    data = (await ac.get(f"{U}/churn-risk", headers=h)).json()["data"]
    assert data["method"] == "rules" and "language model" in data["note"]
    top = data["items"][0]
    assert top["member_id"] == quiet["id"] and top["level"] in ("medium", "high")
    assert any("No visits" in r for r in top["reasons"]) and top["suggested_action"]
    assert data["items"][0]["score"] > next(i["score"] for i in data["items"] if i["member_id"] == busy["id"])


@pytest.mark.asyncio
async def test_attendance_equipment_and_summary_use_real_records(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    await _door(ac, h, member)
    att = (await ac.get(f"{U}/attendance", headers=h)).json()["data"]
    assert att["visits"] == 1 and sum(att["by_weekday"].values()) == 1 and att["notes"]
    assert (await ac.get(f"{U}/attendance?weeks=1", headers=h)).status_code == 422
    eq = (await ac.post("/api/v1/gym/equipment", headers=h, json={"name": "Treadmill 2"})).json()["data"]
    for fault in ("Belt slipping", "Display dead"):
        t = (await ac.post(f"/api/v1/gym/equipment/{eq['id']}/faults", headers=h, json={"fault": fault})).json()["data"]
        await ac.post(f"/api/v1/gym/maintenance/{t['id']}/close", headers=h, json={"resolution": "Repaired it"})
    items = (await ac.get(f"{U}/equipment", headers=h)).json()["data"]["items"]
    assert items[0]["name"] == "Treadmill 2" and items[0]["faults_90d"] == 2 and "Second fault" in items[0]["flags"][0]
    s = (await ac.get(f"{U}/summary", headers=h)).json()["data"]
    assert s["this_period"]["visits"] == 1 and s["this_period"]["sold"] == 1 and len(s["bullets"]) == 5


@pytest.mark.asyncio
async def test_workout_draft_comes_from_the_gyms_own_library_and_is_not_saved(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    member = await _member(ac, h)
    body = {"member_id": member["id"], "goal": "muscle", "level": "beginner", "days_per_week": 3}
    assert (await ac.post(f"{U}/workout-draft", headers=h, json=body)).status_code == 409  # empty library
    for name, group in (("Squat", "Legs"), ("Bench press", "Chest"), ("Row", "Back")):
        r = await ac.post("/api/v1/gym/exercises", headers=h, json={"name": name, "muscle_group": group})
        assert r.status_code == 200
    d = (await ac.post(f"{U}/workout-draft", headers=h, json=body)).json()["data"]
    assert d["draft"] is True and d["review_required"] is True and "Not medical advice" in d["disclaimer"]
    assert {ln["exercise"] for ln in d["lines"]} == {"Squat", "Bench press", "Row"}
    assert all(ln["sets"] == 2 and ln["reps"] == 10 for ln in d["lines"])  # beginner: one set fewer than 3
    assert "shoulders" in d["muscle_groups_missing_from_library"]
    assert (await ac.get("/api/v1/gym/programmes", headers=h)).json()["data"] == []
    assert (await ac.post(f"{U}/workout-draft", headers=h, json={**body, "days_per_week": 9})).status_code == 422


@pytest.mark.asyncio
async def test_a_manager_can_switch_insights_off_and_tenants_stay_separate(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    assert (await ac.get(f"{U}/status", headers=h)).json()["data"]["insights_enabled"] is True
    assert (await ac.post(f"{U}/status", headers=h, json={"insights_enabled": False})).status_code == 200
    for path in ("summary", "churn-risk", "attendance", "equipment"):
        r = await ac.get(f"{U}/{path}", headers=h)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "GYM_INSIGHTS_OFF"
    member = await _member(ac, h)
    assert (await ac.post(f"{U}/workout-draft", headers=h, json={"member_id": member["id"], "goal": "muscle"})).status_code == 403
    db_session.add(m.GymSettings(tenant_id=seed["t2"].id, insights_enabled=False))
    await db_session.commit()
    assert (await ac.post(f"{U}/status", headers=h, json={"insights_enabled": True})).status_code == 200
    assert (await ac.get(f"{U}/summary", headers=h)).status_code == 200
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get(f"{U}/churn-risk", headers=h)).status_code == 403
