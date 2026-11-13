"""HR notices go to one person each: the manager or HR when something waits, the person when it is decided."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_leave_steps import _login_staff

pytestmark = pytest.mark.asyncio


async def _hr(ac, headers) -> list[dict]:
    return (await ac.get("/api/v1/notifications?category=hr", headers=headers)).json()["data"]


async def test_leave_and_payslip_notices_reach_the_right_people(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    boss = await _person(ac, h, email="boss@alpha.example.com")
    await _person(ac, h, email="worker@alpha.example.com", manager_id=boss["id"])
    await _person(ac, h, email="other@alpha.example.com")
    boss_h = await _login_staff(ac, h, "boss@alpha.example.com", "Ama Boss")
    worker_h = await _login_staff(ac, h, "worker@alpha.example.com", "Kojo Worker")
    other_h = await _login_staff(ac, h, "other@alpha.example.com", "Esi Other")

    leave = (
        await ac.post("/api/v1/hrm/leave", headers=worker_h, json={"leave_type": "annual", "starts_on": "2027-02-01", "ends_on": "2027-02-03"})
    ).json()["data"]
    assert [n["title"] for n in await _hr(ac, boss_h)] == ["Leave to decide"]
    assert await _hr(ac, other_h) == []
    assert (await ac.post(f"/api/v1/hrm/leave/{leave['id']}/decide", headers=boss_h, json={"approve": True})).status_code == 200
    assert any(n["title"] == "Leave to decide" for n in await _hr(ac, h))
    assert (await ac.post(f"/api/v1/hrm/leave/{leave['id']}/decide", headers=h, json={"approve": True})).status_code == 200
    mine = await _hr(ac, worker_h)
    assert [n["title"] for n in mine] == ["Leave approved"]

    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-03"})).json()["data"]
    assert (await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)).status_code == 200
    titles = [n["title"] for n in await _hr(ac, other_h)]
    assert titles == ["Payslip ready"]
    # Every HR notice is addressed to one person; none is company-wide, and none shows pay.
    rows = (await db_session.execute(select(m.Notification).where(m.Notification.category == "hr"))).scalars().all()
    assert rows and all(r.user_id for r in rows)
    assert all("GH" not in (r.message or "") and "net" not in (r.message or "").lower() for r in rows)
