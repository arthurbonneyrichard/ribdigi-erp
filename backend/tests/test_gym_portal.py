"""Gym member portal (private link) and trainer portal."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _member, _open, _plan, _sell
from tests.test_gym_fitness import _exercise, _programme
from tests.test_gym_stage1 import _soon, _trainer

P = "/api/v1/public/gym-member"


async def _link(ac, h, member, **extra):
    r = await ac.post(f"/api/v1/gym/members/{member['id']}/portal-link", headers=h, json=extra)
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


def _t(token):
    return {"X-Portal-Token": token}


async def _active_member(ac, h):
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _sell(ac, h, member, plan)
    return member


@pytest.mark.asyncio
async def test_a_link_works_once_issued_expires_and_is_cancelled_by_a_new_one(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    member = await _active_member(ac, h)
    assert (await ac.get(f"{P}/me")).status_code == 401
    assert (await ac.get(f"{P}/me", headers=_t("gmp_nonsense"))).status_code == 401
    first = await _link(ac, h, member)
    me = await ac.get(f"{P}/me", headers=_t(first))
    assert me.status_code == 200 and me.json()["data"]["state"] == "active" and "notes" not in me.json()["data"]
    row = (await db_session.execute(select(m.GymPortalLink))).scalars().first()
    assert row.token_hash != first
    second = await _link(ac, h, member)
    assert (await ac.get(f"{P}/me", headers=_t(first))).status_code == 401
    assert (await ac.get(f"{P}/me", headers=_t(second))).status_code == 200
    link = (await db_session.execute(select(m.GymPortalLink).where(m.GymPortalLink.status == "active"))).scalar_one()
    link.expires_at = datetime.utcnow() - timedelta(minutes=1)
    await db_session.commit()
    assert (await ac.get(f"{P}/me", headers=_t(second))).status_code == 401
    third = await _link(ac, h, member)
    assert (await ac.post(f"/api/v1/gym/members/{member['id']}/portal-link/revoke", headers=h)).json()["data"]["revoked"] == 1
    assert (await ac.get(f"{P}/me", headers=_t(third))).status_code == 401
    assert (await ac.post(f"/api/v1/gym/members/{member['id']}/portal-link", headers=h, json={"days": 90})).status_code == 422


@pytest.mark.asyncio
async def test_member_books_and_cancels_only_their_own_and_never_sees_other_names(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    a, b = await _active_member(ac, h), await _active_member(ac, h)
    cls = (await ac.post("/api/v1/gym/classes", headers=h, json={"name": "Yoga", "starts_at": _soon(), "capacity": 5})).json()["data"]
    ta, tb = await _link(ac, h, a), await _link(ac, h, b)
    booked = await ac.post(f"{P}/classes/{cls['id']}/book", headers=_t(ta), json={})
    assert booked.status_code == 200, booked.text
    mine = booked.json()["data"][0]
    assert mine["my_status"] == "booked" and mine["places_left"] == 4
    assert (await ac.post(f"{P}/classes/{cls['id']}/book", headers=_t(ta), json={})).status_code == 409
    other_view = (await ac.get(f"{P}/classes", headers=_t(tb))).json()["data"][0]
    assert other_view["my_status"] is None and a["full_name"] not in str(other_view)
    assert (await ac.post(f"{P}/bookings/{mine['my_booking_id']}/cancel", headers=_t(tb))).status_code == 404
    done = await ac.post(f"{P}/bookings/{mine['my_booking_id']}/cancel", headers=_t(ta))
    assert done.status_code == 200 and done.json()["data"][0]["my_status"] is None
    assert (await ac.post(f"{P}/bookings/{mine['my_booking_id']}/cancel", headers=_t(ta))).status_code == 409


@pytest.mark.asyncio
async def test_member_sees_own_fitness_logs_workouts_and_cannot_touch_anyone_elses(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    a, b = await _active_member(ac, h), await _active_member(ac, h)
    ex = await _exercise(ac, h)
    prog = (await _programme(ac, h, a, [ex])).json()["data"]
    await ac.post(f"/api/v1/gym/members/{a['id']}/measurements", headers=h, json={"weight_kg": 80, "height_cm": 180})
    plan = (await ac.post("/api/v1/gym/nutrition-plans", headers=h, json={"member_id": a["id"], "name": "Plan", "calories": 2000, "starts_on": date.today().isoformat()})).json()["data"]
    ta, tb = await _link(ac, h, a), await _link(ac, h, b)
    assert len((await ac.get(f"{P}/programmes", headers=_t(ta))).json()["data"]) == 1
    assert (await ac.get(f"{P}/programmes", headers=_t(tb))).json()["data"] == []
    assert (await ac.get(f"{P}/measurements", headers=_t(ta))).json()["data"]["items"][0]["bmi"] == 24.7
    line = prog["lines"][0]["id"]
    ok = await ac.post(f"{P}/programmes/{prog['id']}/workouts", headers=_t(ta), json={"line_id": line, "sets_done": 3, "reps_done": 30})
    assert ok.status_code == 200 and ok.json()["data"]["lines"][0]["times_done"] == 1
    assert (await ac.post(f"{P}/programmes/{prog['id']}/workouts", headers=_t(tb), json={"line_id": line, "sets_done": 1, "reps_done": 1})).status_code == 404
    assert (await ac.post(f"{P}/nutrition-plans/{plan['id']}/intake", headers=_t(tb), json={"calories": 1})).status_code == 404
    assert (await ac.post(f"{P}/nutrition-plans/{plan['id']}/intake", headers=_t(ta), json={"calories": 1800})).status_code == 200
    pay = (await ac.get(f"{P}/payments", headers=_t(ta))).json()["data"]
    assert len(pay) == 1 and pay[0]["kind"]


@pytest.mark.asyncio
async def test_portal_door_code_rotates_and_feedback_reaches_staff(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    a = await _active_member(ac, h)
    tok = await _link(ac, h, a)
    first_code = (await ac.post(f"{P}/door-code", headers=_t(tok))).json()["data"]
    assert first_code["qr_png"].startswith("data:image/png;base64,")
    c1 = first_code["token"]
    assert (await ac.post("/api/v1/gym/check-ins/scan", headers=h, json={"token": c1})).json()["data"]["allowed"] is True
    c2 = (await ac.post(f"{P}/door-code", headers=_t(tok))).json()["data"]["token"]
    old = (await ac.post("/api/v1/gym/check-ins/scan", headers=h, json={"token": c1})).json()["data"]
    assert old["allowed"] is False
    assert (await ac.post("/api/v1/gym/check-ins/scan", headers=h, json={"token": c2})).json()["data"]["allowed"] is True
    trainer = await _trainer(ac, h)
    assert (await ac.post(f"{P}/feedback", headers=_t(tok), json={"kind": "rating"})).status_code == 422
    assert (await ac.post(f"{P}/feedback", headers=_t(tok), json={"kind": "complaint"})).status_code == 422
    assert (await ac.post(f"{P}/feedback", headers=_t(tok), json={"kind": "rating", "rating": 4, "trainer_id": trainer["id"]})).status_code == 200
    assert (await ac.post(f"{P}/feedback", headers=_t(tok), json={"kind": "rating", "rating": 5, "trainer_id": str(uuid4())})).status_code == 404
    sent = await ac.post(f"{P}/feedback", headers=_t(tok), json={"kind": "complaint", "message": "The showers were cold"})
    assert sent.status_code == 200
    rows = (await ac.get("/api/v1/gym/feedback?status=open", headers=h)).json()["data"]
    assert len(rows) == 2
    fid = next(r["id"] for r in rows if r["kind"] == "complaint")
    assert (await ac.post(f"/api/v1/gym/feedback/{fid}/close", headers=h, json={"resolution": "Heater fixed"})).status_code == 200
    assert (await ac.post(f"/api/v1/gym/feedback/{fid}/close", headers=h, json={"resolution": "Heater fixed"})).status_code == 409
    assert (await ac.get("/api/v1/gym/reports/trainer-ratings", headers=h)).json()["data"][0]["average"] == 4.0
    assert (await ac.post(f"{P}/consent", headers=_t(tok), json={"consent": True})).json()["data"]["marketing_consent"] is True


@pytest.mark.asyncio
async def test_a_link_stops_working_when_the_company_is_not_a_gym_and_never_crosses_tenants(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    member = await _member(ac, h)
    tok = await _link(ac, h, member)
    other = m.GymMember(tenant_id=seed["t2"].id, member_number="GM-1", full_name="Theirs", joined_on=date.today())
    db_session.add(other)
    await db_session.commit()
    assert (await ac.post(f"/api/v1/gym/members/{other.id}/portal-link", headers=h, json={})).status_code == 404
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    assert (await ac.get(f"{P}/me", headers=_t(tok))).status_code == 401


@pytest.mark.asyncio
async def test_trainer_portal_shows_only_own_work(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    mine, theirs = await _active_member(ac, h), await _active_member(ac, h)
    t1, t2 = await _trainer(ac, h), await _trainer(ac, h)
    admin_user = (await db_session.execute(select(m.User).where(m.User.email == "admin@alpha.example.com"))).scalar_one()
    assert (await ac.get("/api/v1/gym/trainer-portal/me", headers=h)).status_code == 404  # not linked yet
    assert (await ac.post(f"/api/v1/gym/trainers/{t1['id']}/link-user", headers=h, json={"user_id": admin_user.id})).status_code == 200
    assert (await ac.post(f"/api/v1/gym/trainers/{t2['id']}/link-user", headers=h, json={"user_id": admin_user.id})).status_code == 409
    for trainer, member in ((t1, mine), (t2, theirs)):
        r = await ac.post("/api/v1/gym/training-sessions", headers=h, json={"trainer_id": trainer["id"], "member_id": member["id"], "starts_at": _soon(3), "minutes": 60})
        assert r.status_code == 200, r.text
    me = (await ac.get("/api/v1/gym/trainer-portal/me", headers=h)).json()["data"]
    assert me["members"] == 1 and me["upcoming_sessions"] == 1
    sessions = (await ac.get("/api/v1/gym/trainer-portal/sessions", headers=h)).json()["data"]
    assert [s["member_id"] for s in sessions] == [mine["id"]]
    assert [x["id"] for x in (await ac.get("/api/v1/gym/trainer-portal/members", headers=h)).json()["data"]] == [mine["id"]]
    base = "/api/v1/gym/trainer-portal/members"
    assert (await ac.get(f"{base}/{theirs['id']}/measurements", headers=h)).status_code == 404
    assert (await ac.post(f"{base}/{theirs['id']}/measurements", headers=h, json={"weight_kg": 70})).status_code == 404
    assert (await ac.post(f"{base}/{mine['id']}/measurements", headers=h, json={"weight_kg": 70})).status_code == 200
    other = (await db_session.execute(select(m.GymTrainingSession).where(m.GymTrainingSession.trainer_id == t2["id"]))).scalar_one()
    assert (await ac.post(f"/api/v1/gym/trainer-portal/sessions/{other.id}", headers=h, json={"status": "completed"})).status_code == 404
    own = sessions[0]["id"]
    assert (await ac.post(f"/api/v1/gym/trainer-portal/sessions/{own}", headers=h, json={"status": "completed"})).status_code == 200
