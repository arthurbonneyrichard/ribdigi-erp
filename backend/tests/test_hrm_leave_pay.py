"""Leave encashment: days off the balance at once, paid on the chosen month's payroll at the daily rate."""

from __future__ import annotations

from datetime import date

import pytest

from tests.test_hrm_desk import _admin, _even, _person

pytestmark = pytest.mark.asyncio
YEAR = date.today().year


async def test_unused_leave_paid_on_payroll_and_off_the_balance(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, basic=2200, allowances=0)
    before = (await ac.get(f"/api/v1/hrm/employees/{person['id']}/leave-balance", headers=h)).json()["data"]
    too_many = await ac.post("/api/v1/hrm/leave-encashments", headers=h, json={"employee_id": person["id"], "year": YEAR, "days": before["left"] + 1, "period": "2026-04"})
    assert too_many.status_code == 409
    ok = await ac.post("/api/v1/hrm/leave-encashments", headers=h, json={"employee_id": person["id"], "year": YEAR, "days": 5, "period": "2026-04"})
    assert ok.status_code == 200, ok.text
    row = ok.json()["data"]
    assert row["day_rate"] == 100 and row["amount"] == 500  # 2,200 / 22 working days × 5
    after = (await ac.get(f"/api/v1/hrm/employees/{person['id']}/leave-balance", headers=h)).json()["data"]
    assert after["left"] == before["left"] - 5

    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-04"})).json()["data"]
    slip = next(s for s in run["slips"] if s["employee_id"] == person["id"])
    assert slip["leave_pay"] == 500 and slip["gross"] == 2700 and slip["ssnit_employee"] == 121
    assert (await ac.post(f"/api/v1/hrm/leave-encashments/{row['id']}/cancel", headers=h)).status_code == 409
    assert (await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)).status_code == 200
    listed = (await ac.get("/api/v1/hrm/leave-encashments", headers=h)).json()["data"]
    assert listed[0]["status"] == "paid"
    await _even(ac, h)


async def test_cancel_gives_the_days_back(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h)
    before = (await ac.get(f"/api/v1/hrm/employees/{person['id']}/leave-balance", headers=h)).json()["data"]["left"]
    row = (await ac.post("/api/v1/hrm/leave-encashments", headers=h, json={"employee_id": person["id"], "year": YEAR, "days": 2, "period": "2026-05"})).json()["data"]
    assert (await ac.post(f"/api/v1/hrm/leave-encashments/{row['id']}/cancel", headers=h)).status_code == 200
    assert (await ac.get(f"/api/v1/hrm/employees/{person['id']}/leave-balance", headers=h)).json()["data"]["left"] == before
