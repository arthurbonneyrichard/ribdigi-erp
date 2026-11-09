"""Gym desk: members, plans, the door, classes and its own till."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import gym
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "gym")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _plan(ac, h, *, price=300, days=30, visits=None):
    r = await ac.post(
        "/api/v1/gym/plans", headers=h,
        json={"name": f"Plan {uuid4().hex[:5]}", "price": price, "duration_days": days, "visit_limit": visits},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _member(ac, h):
    r = await ac.post("/api/v1/gym/members", headers=h, json={"full_name": f"Ama {uuid4().hex[:5]}"})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _open(ac, h):
    r = await ac.post("/api/v1/gym/till/shift/open", headers=h, json={"opening_cash": 100})
    assert r.status_code == 200, r.text


async def _sell(ac, h, member, plan, method="cash"):
    r = await ac.post(
        "/api/v1/gym/memberships", headers=h, json={"member_id": member["id"], "plan_id": plan["id"], "method": method}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _door(ac, h, member):
    r = await ac.post("/api/v1/gym/check-ins", headers=h, json={"member_id": member["id"]})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _even(ac, h):
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)


@pytest.mark.asyncio
async def test_selling_needs_an_open_till_and_books_the_money(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    plan, member = await _plan(ac, h), await _member(ac, h)
    closed = await ac.post("/api/v1/gym/memberships", headers=h, json={"member_id": member["id"], "plan_id": plan["id"], "method": "cash"})
    assert closed.status_code == 409
    await _open(ac, h)
    sold = await _sell(ac, h, member, plan)
    assert sold["starts_on"] == date.today().isoformat()
    assert sold["ends_on"] == (date.today() + timedelta(days=29)).isoformat()
    await _even(ac, h)
    shift = (await ac.get("/api/v1/gym/till/shift", headers=h)).json()["data"]
    assert shift["expected_cash"] == round(100 + sold["total"], 2)
    assert (await db_session.execute(select(m.Transaction).where(m.Transaction.tenant_id == seed["t1"].id))).first() is None


@pytest.mark.asyncio
async def test_renewal_starts_after_the_current_one_so_no_days_are_lost(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _open(ac, h)
    first = await _sell(ac, h, member, plan)
    second = await _sell(ac, h, member, plan)
    assert second["starts_on"] == (date.fromisoformat(first["ends_on"]) + timedelta(days=1)).isoformat()


@pytest.mark.asyncio
async def test_the_door_lets_members_in_once_a_day_and_refuses_with_a_reason(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    plan, member = await _plan(ac, h), await _member(ac, h)
    refused = await _door(ac, h, member)
    assert refused["allowed"] is False and "No membership" in refused["message"]
    await _open(ac, h)
    await _sell(ac, h, member, plan)
    assert (await _door(ac, h, member))["allowed"] is True
    again = await _door(ac, h, member)
    assert again["already_in"] is True
    rows = (await ac.get("/api/v1/gym/check-ins", headers=h)).json()["data"]
    assert sum(1 for r in rows if r["allowed"]) == 1 and sum(1 for r in rows if not r["allowed"]) == 1


@pytest.mark.asyncio
async def test_an_ended_membership_is_refused(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _open(ac, h)
    sold = await _sell(ac, h, member, plan)
    row = await db_session.get(m.GymMembership, sold["id"])
    row.starts_on, row.ends_on = date.today() - timedelta(days=40), date.today() - timedelta(days=10)
    await db_session.commit()
    result = await _door(ac, h, member)
    assert result["allowed"] is False and "ended" in result["message"]


@pytest.mark.asyncio
async def test_a_visit_pack_runs_out(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    plan, member = await _plan(ac, h, visits=1), await _member(ac, h)
    await _open(ac, h)
    sold = await _sell(ac, h, member, plan)
    assert (await _door(ac, h, member))["allowed"] is True
    for row in (await db_session.execute(select(m.GymCheckIn).where(m.GymCheckIn.membership_id == sold["id"]))).scalars():
        row.checked_in_at = datetime.utcnow() - timedelta(days=2)
    await db_session.commit()
    result = await _door(ac, h, member)
    assert result["allowed"] is False and "No visits" in result["message"]


@pytest.mark.asyncio
async def test_freezing_blocks_the_door_and_gives_the_days_back(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _open(ac, h)
    sold = await _sell(ac, h, member, plan)
    assert (await ac.post(f"/api/v1/gym/memberships/{sold['id']}/freeze", headers=h)).status_code == 200
    assert (await _door(ac, h, member))["allowed"] is False
    row = await db_session.get(m.GymMembership, sold["id"])
    row.frozen_on = date.today() - timedelta(days=5)
    await db_session.commit()
    r = await ac.post(f"/api/v1/gym/memberships/{sold['id']}/unfreeze", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["data"]["ends_on"] == (date.fromisoformat(sold["ends_on"]) + timedelta(days=5)).isoformat()


@pytest.mark.asyncio
async def test_cancel_refund_is_capped_and_reverses_the_books(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    plan, member = await _plan(ac, h), await _member(ac, h)
    await _open(ac, h)
    sold = await _sell(ac, h, member, plan)
    url = f"/api/v1/gym/memberships/{sold['id']}/cancel"
    too_much = await ac.post(url, headers=h, json={"reason": "Moved away", "refund": sold["total"] + 1, "method": "cash"})
    assert too_much.status_code == 422
    r = await ac.post(url, headers=h, json={"reason": "Moved away", "refund": 100, "method": "cash"})
    assert r.status_code == 200, r.text
    assert (await ac.post(url, headers=h, json={"reason": "Moved away"})).status_code == 409
    shift = (await ac.get("/api/v1/gym/till/shift", headers=h)).json()["data"]
    assert shift["expected_cash"] == round(100 + sold["total"] - 100, 2)
    assert (await _door(ac, h, member))["allowed"] is False
    await _even(ac, h)


@pytest.mark.asyncio
async def test_class_capacity_and_membership_rules(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    plan = await _plan(ac, h)
    a, b, c = await _member(ac, h), await _member(ac, h), await _member(ac, h)
    await _open(ac, h)
    await _sell(ac, h, a, plan)
    await _sell(ac, h, b, plan)
    starts = (datetime.utcnow() + timedelta(days=1)).isoformat()
    cls = (await ac.post("/api/v1/gym/classes", headers=h, json={"name": "Spin", "starts_at": starts, "capacity": 1})).json()["data"]
    url = f"/api/v1/gym/classes/{cls['id']}/book"
    assert (await ac.post(url, headers=h, json={"member_id": c["id"]})).status_code == 409
    booked = await ac.post(url, headers=h, json={"member_id": a["id"]})
    assert booked.status_code == 200 and booked.json()["data"]["booked"] == 1
    assert (await ac.post(url, headers=h, json={"member_id": a["id"]})).status_code == 409
    full = await ac.post(url, headers=h, json={"member_id": b["id"]})
    assert full.status_code == 409 and "full" in full.text
    booking = booked.json()["data"]["bookings"][0]["id"]
    assert (await ac.post(f"/api/v1/gym/bookings/{booking}", headers=h, json={"status": "cancelled"})).status_code == 200
    assert (await ac.post(url, headers=h, json={"member_id": b["id"]})).status_code == 200


@pytest.mark.asyncio
async def test_reports_expiring_and_tax(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    plan, member = await _plan(ac, h, days=5), await _member(ac, h)
    await _open(ac, h)
    sold = await _sell(ac, h, member, plan, method="mobile_money")
    await _door(ac, h, member)
    data = (await ac.get("/api/v1/gym/reports", headers=h)).json()["data"]
    assert data["sold"] == 1 and data["visits"] == 1 and data["active_members"] == 1
    assert data["takings"] == sold["total"] and data["by_method"]["mobile_money"] == sold["total"]
    today = (await ac.get("/api/v1/gym/today", headers=h)).json()["data"]
    assert today["expiring"][0]["member_id"] == member["id"]
    row = await db_session.get(m.GymMembership, sold["id"])
    tax = (await ac.get("/api/v1/reports/tax", headers=h)).json()["data"]
    assert tax["output_tax"] == float(row.tax)


def test_each_role_has_its_own_job():
    from fastapi import HTTPException

    def can(role, area):
        try:
            gym.job({"role": role}, area)
            return True
        except HTTPException:
            return False

    assert can("gym_frontdesk", "desk") and can("gym_frontdesk", "door") and not can("gym_frontdesk", "correct")
    assert can("gym_trainer", "classes") and can("gym_trainer", "door")
    assert not can("gym_trainer", "desk") and not can("gym_trainer", "correct")
    assert can("gym_manager", "correct")


@pytest.mark.asyncio
async def test_other_desks_are_shut_both_ways(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    assert (await ac.get("/api/v1/pos/sessions", headers=h)).status_code == 403
    assert (await ac.get("/api/v1/hotel/summary", headers=h)).status_code == 403
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/gym/today", headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_one_gym_cannot_touch_anothers_members(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    theirs = m.GymMember(tenant_id=seed["t2"].id, member_number="GM-X", full_name="Theirs", joined_on=date.today())
    db_session.add(theirs)
    await db_session.commit()
    assert (await ac.post("/api/v1/gym/check-ins", headers=h, json={"member_id": theirs.id})).status_code == 404
