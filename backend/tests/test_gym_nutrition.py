"""Gym nutrition plans and daily intake."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _member


def _body(member, **extra):
    body = {"member_id": member["id"], "name": "Lean bulk", "calories": 2800, "protein_g": 160, "starts_on": (date.today() - timedelta(days=1)).isoformat()}
    body.update(extra)
    return body


@pytest.mark.asyncio
async def test_plan_one_live_per_member_and_intake_once_a_day(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    member = await _member(ac, h)
    made = await ac.post("/api/v1/gym/nutrition-plans", headers=h, json=_body(member, allergies="Peanuts"))
    assert made.status_code == 200, made.text
    plan = made.json()["data"]
    assert plan["targets"]["calories"] == 2800 and plan["allergies"] == "Peanuts"
    assert (await ac.post("/api/v1/gym/nutrition-plans", headers=h, json=_body(member))).status_code == 409
    url = f"/api/v1/gym/nutrition-plans/{plan['id']}/intake"
    ok = await ac.post(url, headers=h, json={"calories": 2500, "water_ml": 2000})
    assert ok.status_code == 200 and len(ok.json()["data"]["logs"]) == 1
    assert (await ac.post(url, headers=h, json={"calories": 100})).status_code == 409
    assert (await ac.post(url, headers=h, json={})).status_code == 422
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert (await ac.post(url, headers=h, json={"calories": 1, "logged_on": tomorrow})).status_code == 422
    assert (await ac.post(f"/api/v1/gym/nutrition-plans/{plan['id']}/status", headers=h, json={"status": "completed"})).status_code == 200
    assert (await ac.post(url, headers=h, json={"calories": 1, "logged_on": (date.today() - timedelta(days=1)).isoformat()})).status_code == 409
    assert (await ac.post("/api/v1/gym/nutrition-plans", headers=h, json=_body(member, name="Cut"))).status_code == 200


@pytest.mark.asyncio
async def test_plan_validation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    member = await _member(ac, h)
    empty = {"member_id": member["id"], "name": "Empty plan", "starts_on": date.today().isoformat()}
    assert (await ac.post("/api/v1/gym/nutrition-plans", headers=h, json=empty)).status_code == 422
    bad_end = _body(member, ends_on=(date.today() - timedelta(days=9)).isoformat())
    assert (await ac.post("/api/v1/gym/nutrition-plans", headers=h, json=bad_end)).status_code == 422
    assert (await ac.post("/api/v1/gym/nutrition-plans", headers=h, json=_body(member, calories=-5))).status_code == 422


@pytest.mark.asyncio
async def test_nutrition_is_tenant_scoped_and_gym_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    other = m.GymMember(tenant_id=seed["t2"].id, member_number="GM-0001", full_name="Theirs", joined_on=date.today())
    db_session.add(other)
    await db_session.commit()
    theirs = m.GymNutritionPlan(tenant_id=seed["t2"].id, member_id=other.id, name="Theirs", calories=2000, starts_on=date.today())
    db_session.add(theirs)
    await db_session.commit()
    mine = await _member(ac, h)
    assert (await ac.post("/api/v1/gym/nutrition-plans", headers=h, json=_body({"id": other.id}))).status_code == 404
    assert (await ac.post(f"/api/v1/gym/nutrition-plans/{theirs.id}/intake", headers=h, json={"calories": 1})).status_code == 404
    assert (await ac.post(f"/api/v1/gym/nutrition-plans/{theirs.id}/status", headers=h, json={"status": "cancelled"})).status_code == 404
    assert (await ac.get("/api/v1/gym/nutrition-plans", headers=h)).json()["data"] == []
    await ac.post("/api/v1/gym/nutrition-plans", headers=h, json=_body(mine))
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/gym/nutrition-plans", headers=h)).status_code == 403
