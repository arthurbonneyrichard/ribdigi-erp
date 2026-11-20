"""Gym fitness: exercise library, workout programmes, workout logs, body measurements."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app import gym
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _member


async def _exercise(ac, h, name=None):
    r = await ac.post("/api/v1/gym/exercises", headers=h, json={"name": name or f"Squat {uuid4().hex[:5]}", "muscle_group": "Legs"})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _programme(ac, h, member, exercises, **extra):
    body = {
        "member_id": member["id"], "name": "Starter strength", "starts_on": (date.today() - timedelta(days=2)).isoformat(),
        "lines": [{"exercise_id": e["id"], "day_of_week": i + 1, "sets": 3, "reps": 10, "weight_kg": 20} for i, e in enumerate(exercises)],
    }
    body.update(extra)
    return await ac.post("/api/v1/gym/programmes", headers=h, json=body)


@pytest.mark.asyncio
async def test_exercise_library_rejects_duplicates_and_junk(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _exercise(ac, h, "Deadlift")
    assert (await ac.post("/api/v1/gym/exercises", headers=h, json={"name": "deadlift"})).status_code == 409
    assert (await ac.post("/api/v1/gym/exercises", headers=h, json={"name": "!!!"})).status_code in (400, 422)


@pytest.mark.asyncio
async def test_programme_is_built_logged_once_a_day_and_closed(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    member = await _member(ac, h)
    ex = [await _exercise(ac, h), await _exercise(ac, h)]
    made = await _programme(ac, h, member, ex)
    assert made.status_code == 200, made.text
    prog = made.json()["data"]
    assert len(prog["lines"]) == 2 and prog["lines"][0]["times_done"] == 0
    line = prog["lines"][0]["id"]
    ok = await ac.post(f"/api/v1/gym/programmes/{prog['id']}/workouts", headers=h, json={"line_id": line, "sets_done": 3, "reps_done": 30, "weight_kg": 22.5})
    assert ok.status_code == 200 and ok.json()["data"]["lines"][0]["times_done"] == 1
    dup = await ac.post(f"/api/v1/gym/programmes/{prog['id']}/workouts", headers=h, json={"line_id": line, "sets_done": 3, "reps_done": 30})
    assert dup.status_code == 409
    future = (date.today() + timedelta(days=1)).isoformat()
    assert (await ac.post(f"/api/v1/gym/programmes/{prog['id']}/workouts", headers=h, json={"line_id": line, "done_on": future, "sets_done": 1, "reps_done": 1})).status_code == 422
    hist = (await ac.get(f"/api/v1/gym/members/{member['id']}/workouts", headers=h)).json()["data"]
    assert len(hist) == 1 and hist[0]["weight_kg"] == 22.5
    assert (await ac.post(f"/api/v1/gym/programmes/{prog['id']}/status", headers=h, json={"status": "completed"})).status_code == 200
    assert (await ac.post(f"/api/v1/gym/programmes/{prog['id']}/status", headers=h, json={"status": "cancelled"})).status_code == 409
    late = await ac.post(
        f"/api/v1/gym/programmes/{prog['id']}/workouts", headers=h,
        json={"line_id": prog["lines"][1]["id"], "sets_done": 3, "reps_done": 30},
    )
    assert late.status_code == 409


@pytest.mark.asyncio
async def test_programme_validation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    member = await _member(ac, h)
    ex = await _exercise(ac, h)
    bad_end = await _programme(ac, h, member, [ex], ends_on=(date.today() - timedelta(days=30)).isoformat())
    assert bad_end.status_code == 422
    assert (await _programme(ac, h, member, [])).status_code == 422
    unknown = await ac.post(
        "/api/v1/gym/programmes", headers=h,
        json={"member_id": member["id"], "name": "X plan", "starts_on": date.today().isoformat(), "lines": [{"exercise_id": str(uuid4())}]},
    )
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_measurements_compute_bmi_keep_height_and_show_change(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    member = await _member(ac, h)
    path = f"/api/v1/gym/members/{member['id']}/measurements"
    assert (await ac.post(path, headers=h, json={})).status_code == 422
    first = await ac.post(path, headers=h, json={"measured_on": (date.today() - timedelta(days=30)).isoformat(), "weight_kg": 90, "height_cm": 180, "waist_cm": 100})
    assert first.status_code == 200, first.text
    assert first.json()["data"]["bmi"] == 27.8
    second = await ac.post(path, headers=h, json={"weight_kg": 85})
    assert second.json()["data"]["height_cm"] == 180 and second.json()["data"]["bmi"] == 26.2
    data = (await ac.get(path, headers=h)).json()["data"]
    assert data["items"][0]["weight_kg"] == 85
    assert data["change_since_first"]["weight_kg"] == -5
    future = (date.today() + timedelta(days=1)).isoformat()
    assert (await ac.post(path, headers=h, json={"weight_kg": 80, "measured_on": future})).status_code == 422
    assert (await ac.post(path, headers=h, json={"weight_kg": 0})).status_code == 422


@pytest.mark.asyncio
async def test_fitness_is_tenant_scoped_and_gym_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    other = m.GymMember(tenant_id=seed["t2"].id, member_number="GM-0001", full_name="Theirs", joined_on=date.today())
    their_ex = m.GymExercise(tenant_id=seed["t2"].id, name="Theirs press")
    db_session.add_all([other, their_ex])
    await db_session.commit()
    mine = await _member(ac, h)
    ex = await _exercise(ac, h)
    assert (await ac.get(f"/api/v1/gym/members/{other.id}/measurements", headers=h)).status_code == 404
    assert (await ac.post(f"/api/v1/gym/members/{other.id}/measurements", headers=h, json={"weight_kg": 70})).status_code == 404
    assert (await _programme(ac, h, other.__dict__ | {"id": other.id}, [ex])).status_code == 404
    assert (await _programme(ac, h, mine, [{"id": their_ex.id}])).status_code == 404
    assert [e["name"] for e in (await ac.get("/api/v1/gym/exercises", headers=h)).json()["data"]] == [ex["name"]]
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    for path in ("exercises", "programmes"):
        assert (await ac.get(f"/api/v1/gym/{path}", headers=h)).status_code == 403


def test_front_desk_cannot_see_body_details_but_trainer_can():
    with pytest.raises(HTTPException) as err:
        gym.job({"role": "gym_frontdesk"}, "fitness")
    assert err.value.status_code == 403
    gym.job({"role": "gym_trainer"}, "fitness")
    gym.job({"role": "company_admin"}, "fitness")
