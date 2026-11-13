"""Cover for a manager's leave approvals while they are away, and escalation to HR."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app import hrm_delegation
from app import models as m
from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_leave_steps import _login_staff

pytestmark = pytest.mark.asyncio
TODAY = date.today()


async def test_cover_decides_the_manager_step(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    boss = await _person(ac, h, email="boss@alpha.example.com")
    deputy = await _person(ac, h, email="deputy@alpha.example.com")
    await _person(ac, h, email="worker@alpha.example.com", manager_id=boss["id"])
    boss_h = await _login_staff(ac, h, "boss@alpha.example.com", "Ama Boss")
    deputy_h = await _login_staff(ac, h, "deputy@alpha.example.com", "Esi Deputy")
    worker_h = await _login_staff(ac, h, "worker@alpha.example.com", "Kojo Worker")

    # A member of staff cannot set cover for someone else.
    other = await ac.post("/api/v1/hrm/cover", headers=deputy_h, json={"from_employee_id": boss["id"], "to_employee_id": deputy["id"], "starts_on": TODAY.isoformat(), "ends_on": TODAY.isoformat()})
    assert other.status_code == 403
    cover = await ac.post(
        "/api/v1/hrm/cover", headers=boss_h,
        json={"to_employee_id": deputy["id"], "starts_on": TODAY.isoformat(), "ends_on": (TODAY + timedelta(days=7)).isoformat(), "reason": "Annual leave"},
    )
    assert cover.status_code == 200, cover.text
    assert cover.json()["data"]["running"]

    leave = (await ac.post("/api/v1/hrm/leave", headers=worker_h, json={"leave_type": "annual", "starts_on": "2027-03-01", "ends_on": "2027-03-02"})).json()["data"]
    notes = (await ac.get("/api/v1/notifications?category=hr", headers=deputy_h)).json()["data"]
    assert any(n["title"] == "Leave to decide" for n in notes)
    assert [r["id"] for r in (await ac.get("/api/v1/hrm/team/leave", headers=deputy_h)).json()["data"]] == [leave["id"]]
    step = await ac.post(f"/api/v1/hrm/leave/{leave['id']}/decide", headers=deputy_h, json={"approve": True})
    assert step.status_code == 200 and step.json()["data"]["stage"] == "hr"

    ended = await ac.post(f"/api/v1/hrm/cover/{cover.json()['data']['id']}/end", headers=boss_h)
    assert ended.status_code == 200 and not ended.json()["data"]["running"]
    second = (await ac.post("/api/v1/hrm/leave", headers=worker_h, json={"leave_type": "annual", "starts_on": "2027-04-05", "ends_on": "2027-04-05"})).json()["data"]
    assert (await ac.post(f"/api/v1/hrm/leave/{second['id']}/decide", headers=deputy_h, json={"approve": True})).status_code == 403


async def test_waiting_leave_is_escalated_once(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    boss = await _person(ac, h, email="boss@alpha.example.com")
    await _person(ac, h, email="worker@alpha.example.com", manager_id=boss["id"])
    worker_h = await _login_staff(ac, h, "worker@alpha.example.com", "Kojo Worker")
    leave = (await ac.post("/api/v1/hrm/leave", headers=worker_h, json={"leave_type": "annual", "starts_on": "2027-05-03", "ends_on": "2027-05-04"})).json()["data"]
    row = await db_session.get(m.HrmLeaveRequest, leave["id"])
    row.created_at = datetime.utcnow() - timedelta(days=10)
    await db_session.commit()
    tid = seed["t1"].id
    assert await hrm_delegation.scan_escalations(db_session, tid) == 1
    assert await hrm_delegation.scan_escalations(db_session, tid) == 0
    await db_session.commit()
    titles = [n["title"] for n in (await ac.get("/api/v1/notifications?category=hr", headers=h)).json()["data"]]
    assert "Leave waiting on a manager" in titles
    rows = (await db_session.execute(select(m.HrmLeaveRequest.escalated_at).where(m.HrmLeaveRequest.id == leave["id"]))).scalar_one()
    assert rows is not None
