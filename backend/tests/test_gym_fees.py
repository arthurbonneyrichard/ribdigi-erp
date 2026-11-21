"""Gym guest and locker fees taken at the till."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _even, _member, _open, _plan, _sell
from tests.test_gym_stage1 import _active


async def _locker(ac, h, number="A1"):
    r = await ac.post("/api/v1/gym/lockers", headers=h, json={"number": number})
    assert r.status_code == 200, r.text
    return r.json()["data"]


@pytest.mark.asyncio
async def test_guest_fee_needs_a_till_and_a_method_and_balances_the_books(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    host = await _active(ac, h)
    free = await ac.post("/api/v1/gym/guests", headers=h, json={"guest_name": "Free Pass", "host_member_id": host["id"]})
    assert free.status_code == 200 and free.json()["data"]["fee"] == 0
    assert (await ac.post("/api/v1/gym/guests", headers=h, json={"guest_name": "Paying Guest", "fee": 20})).status_code == 422  # no method
    paid = await ac.post("/api/v1/gym/guests", headers=h, json={"guest_name": "Paying Guest", "fee": 20, "method": "cash"})
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["fee"] >= 20
    rows = (await db_session.execute(select(m.GymPayment).where(m.GymPayment.kind == "guest_fee"))).scalars().all()
    assert len(rows) == 1 and rows[0].method == "cash"
    await _even(ac, h)
    shift = (await ac.get("/api/v1/gym/till/shift", headers=h)).json()["data"]
    assert shift["expected_cash"] >= 100 + 20


@pytest.mark.asyncio
async def test_guest_fee_with_no_open_till_is_refused_and_nothing_is_booked(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    r = await ac.post("/api/v1/gym/guests", headers=h, json={"guest_name": "No Till", "fee": 20, "method": "cash"})
    assert r.status_code == 409
    assert (await ac.get("/api/v1/gym/guests", headers=h)).json()["data"] == []


@pytest.mark.asyncio
async def test_locker_rental_sets_an_end_date_renews_without_losing_days_and_flags_overdue(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    member = await _active(ac, h)
    lk = await _locker(ac, h)
    assert (await ac.post(f"/api/v1/gym/lockers/{lk['id']}/assign", headers=h, json={"member_id": member["id"], "fee": 30, "method": "cash"})).status_code == 422
    r = await ac.post(f"/api/v1/gym/lockers/{lk['id']}/assign", headers=h, json={"member_id": member["id"], "rental_days": 30, "fee": 30, "method": "mobile_money"})
    assert r.status_code == 200, r.text
    until = date.today() + timedelta(days=29)
    assert r.json()["data"]["rented_until"] == until.isoformat() and r.json()["data"]["overdue"] is False
    renewed = (await ac.post(f"/api/v1/gym/lockers/{lk['id']}/renew", headers=h, json={"rental_days": 30, "fee": 30, "method": "cash"})).json()["data"]
    assert renewed["rented_until"] == (until + timedelta(days=30)).isoformat()
    row = await db_session.get(m.GymLocker, lk["id"])
    row.rented_until = date.today() - timedelta(days=2)
    await db_session.commit()
    assert (await ac.get("/api/v1/gym/lockers", headers=h)).json()["data"][0]["overdue"] is True
    late = (await ac.post(f"/api/v1/gym/lockers/{lk['id']}/renew", headers=h, json={"rental_days": 7, "fee": 10, "method": "cash"})).json()["data"]
    assert late["rented_until"] == (date.today() + timedelta(days=6)).isoformat() and late["overdue"] is False
    fees = (await db_session.execute(select(m.GymPayment).where(m.GymPayment.kind == "locker_fee"))).scalars().all()
    assert len(fees) == 3
    await _even(ac, h)
    assert (await ac.post(f"/api/v1/gym/lockers/{lk['id']}/release", headers=h)).json()["data"]["rented_until"] is None


@pytest.mark.asyncio
async def test_plain_locker_assign_still_works_and_fees_are_tenant_scoped(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    member = await _active(ac, h)
    lk = await _locker(ac, h, "B2")
    ok = await ac.post(f"/api/v1/gym/lockers/{lk['id']}/assign", headers=h, json={"member_id": member["id"]})
    assert ok.status_code == 200 and ok.json()["data"]["rented_until"] is None
    theirs = m.GymLocker(tenant_id=seed["t2"].id, number="Z9", status="taken")
    db_session.add(theirs)
    await db_session.commit()
    assert (await ac.post(f"/api/v1/gym/lockers/{theirs.id}/renew", headers=h, json={"rental_days": 5, "fee": 5, "method": "cash"})).status_code == 404
    free_locker = await _locker(ac, h, "C3")
    assert (await ac.post(f"/api/v1/gym/lockers/{free_locker['id']}/renew", headers=h, json={"rental_days": 5})).status_code == 409
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.post(f"/api/v1/gym/lockers/{lk['id']}/renew", headers=h, json={"rental_days": 5})).status_code == 403
