"""Two-step leave (manager, then HR), leave that builds up month by month, and carry-over."""

from __future__ import annotations

from datetime import date

import pytest

from app import hrm
from tests.conftest import auth_headers
from tests.test_hrm_desk import _admin, _person

pytestmark = pytest.mark.asyncio


def test_earned_days_upfront_and_monthly():
    assert hrm.earned_days(15, date(2020, 1, 1), 2027, accrual="upfront") == 15
    # Started 1 July: half the year.
    assert hrm.earned_days(15, date(2027, 7, 1), 2027, accrual="upfront") == 7
    # Monthly: by the end of March a quarter of 24 days.
    assert hrm.earned_days(24, date(2020, 1, 1), 2027, accrual="monthly", upto=date(2027, 3, 31)) == 6
    assert hrm.earned_days(24, date(2020, 1, 1), 2027, accrual="monthly", upto=date(2028, 1, 5)) == 24
    assert hrm.earned_days(24, date(2028, 1, 1), 2027, accrual="upfront") == 0


async def _login_staff(ac, h, email, name):
    made = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": email, "full_name": name, "password": "SecurePass123!", "role": "hrm_employee"},
    )
    assert made.status_code == 200, made.text
    return await auth_headers(ac, email=email, tenant_slug="alpha")


async def test_manager_then_hr(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    boss = await _person(ac, h, email="boss@alpha.example.com")
    worker = await _person(ac, h, email="worker@alpha.example.com", manager_id=boss["id"])
    other = await _person(ac, h, email="other@alpha.example.com")
    boss_h = await _login_staff(ac, h, "boss@alpha.example.com", "Ama Boss")
    worker_h = await _login_staff(ac, h, "worker@alpha.example.com", "Kojo Worker")
    other_h = await _login_staff(ac, h, "other@alpha.example.com", "Esi Other")

    asked = await ac.post(
        "/api/v1/hrm/leave", headers=worker_h,
        json={"leave_type": "annual", "starts_on": "2027-02-01", "ends_on": "2027-02-03"},
    )
    assert asked.status_code == 200, asked.text
    leave = asked.json()["data"]
    assert leave["stage"] == "manager" and leave["status"] == "pending"

    team = (await ac.get("/api/v1/hrm/team/leave", headers=boss_h)).json()["data"]
    assert [row["id"] for row in team] == [leave["id"]]
    assert (await ac.get("/api/v1/hrm/team/leave", headers=other_h)).json()["data"] == []
    stranger = await ac.post(f"/api/v1/hrm/leave/{leave['id']}/decide", headers=other_h, json={"approve": True})
    assert stranger.status_code == 403

    step1 = await ac.post(f"/api/v1/hrm/leave/{leave['id']}/decide", headers=boss_h, json={"approve": True, "note": "Fine by me"})
    assert step1.status_code == 200, step1.text
    assert step1.json()["data"]["stage"] == "hr" and step1.json()["data"]["status"] == "pending"
    again = await ac.post(f"/api/v1/hrm/leave/{leave['id']}/decide", headers=boss_h, json={"approve": True})
    assert again.status_code == 403  # the manager's step is done; HR decides now

    step2 = await ac.post(f"/api/v1/hrm/leave/{leave['id']}/decide", headers=h, json={"approve": True})
    assert step2.json()["data"]["status"] == "approved"
    assert other["id"]


async def test_no_manager_goes_straight_to_hr_and_no_reporting_loops(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a = await _person(ac, h)
    b = await _person(ac, h, manager_id=a["id"])
    loop = await ac.patch(f"/api/v1/hrm/employees/{a['id']}", headers=h, json={"manager_id": b["id"]})
    assert loop.status_code == 422
    selfish = await ac.patch(f"/api/v1/hrm/employees/{a['id']}", headers=h, json={"manager_id": a["id"]})
    assert selfish.status_code == 422
    leave = await ac.post(
        "/api/v1/hrm/leave", headers=h,
        json={"employee_id": a["id"], "leave_type": "sick", "starts_on": "2027-02-01", "ends_on": "2027-02-01"},
    )
    assert leave.json()["data"]["stage"] == "hr"


async def test_carry_over_and_monthly_limit(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    ok = await ac.patch(
        "/api/v1/hrm/settings", headers=h,
        json={"annual_leave_days": 12, "carry_over_days": 5, "leave_accrual": "monthly"},
    )
    assert ok.status_code == 200, ok.text
    person = await _person(ac, h)
    # Monthly: by the end of February only 2 of 12 days are earned, plus up to 5 carried from 2026 (nothing taken).
    big = await ac.post(
        "/api/v1/hrm/leave", headers=h,
        json={"employee_id": person["id"], "leave_type": "annual", "starts_on": "2027-02-01", "ends_on": "2027-02-12"},
    )
    assert big.status_code == 409
    fits = await ac.post(
        "/api/v1/hrm/leave", headers=h,
        json={"employee_id": person["id"], "leave_type": "annual", "starts_on": "2027-02-01", "ends_on": "2027-02-05"},
    )
    assert fits.status_code == 200, fits.text  # 5 days <= 2 earned + 5 carried
