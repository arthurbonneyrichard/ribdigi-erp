"""HRM desk: staff records, leave, attendance and payroll."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest

from app import hrm
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "hrm")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _person(ac, h, *, basic=3000, allowances=500, **extra):
    r = await ac.post(
        "/api/v1/hrm/employees", headers=h,
        json={"full_name": f"Yaa {uuid4().hex[:5]}", "hired_on": "2024-01-15", "basic_salary": basic, "allowances": allowances, **extra},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _next_monday(weeks=1) -> date:
    d = date.today() + timedelta(days=7 * weeks)
    return d - timedelta(days=d.weekday())


async def _even(ac, h):
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)


def test_paye_runs_band_by_band():
    bands = hrm.DEFAULT_PAYE_BANDS
    assert hrm.paye_on(490, bands) == 0
    assert hrm.paye_on(600, bands) == 5.5
    assert hrm.paye_on(730, bands) == 18.5
    assert hrm.paye_on(1730, bands) == 193.5
    assert hrm.paye_on(100000, bands) > hrm.paye_on(60000, bands)
    assert hrm.paye_on(-5, bands) == 0


def test_working_days_skip_weekends():
    monday = date(2026, 11, 2)
    assert hrm.working_days(monday, monday + timedelta(days=6)) == 5


@pytest.mark.asyncio
async def test_payroll_works_out_ssnit_and_paye_and_books_the_cost(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h)
    r = await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})
    assert r.status_code == 200, r.text
    run = r.json()["data"]
    slip = run["slips"][0]
    assert slip["gross"] == 3500
    assert slip["ssnit_employee"] == 165
    assert slip["taxable"] == 3335
    assert slip["paye"] == hrm.paye_on(3335, hrm.DEFAULT_PAYE_BANDS)
    assert slip["net"] == round(3500 - 165 - slip["paye"], 2)
    assert slip["ssnit_employer"] == 390
    assert (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})).status_code == 409

    approved = await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    assert approved.status_code == 200, approved.text
    await _even(ac, h)
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert "rows" in tb or "accounts" in tb or tb
    assert (await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)).status_code == 409
    assert (await ac.delete(f"/api/v1/hrm/payroll/{run['id']}", headers=h)).status_code == 409


@pytest.mark.asyncio
async def test_each_payment_goes_once_and_finishes_the_run(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h)
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-09"})).json()["data"]
    url = f"/api/v1/hrm/payroll/{run['id']}/pay"
    early = await ac.post(url, headers=h, json={"what": "staff", "method": "bank_transfer"})
    assert early.status_code == 409
    await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    for what in ("staff", "paye"):
        assert (await ac.post(url, headers=h, json={"what": what, "method": "bank_transfer"})).status_code == 200
    again = await ac.post(url, headers=h, json={"what": "staff", "method": "bank_transfer"})
    assert again.status_code == 409
    last = await ac.post(url, headers=h, json={"what": "ssnit", "method": "bank_transfer"})
    assert last.json()["data"]["status"] == "paid"
    await _even(ac, h)


@pytest.mark.asyncio
async def test_bonus_and_deduction_change_the_draft_then_lock(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h)
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-08"})).json()["data"]
    slip = run["slips"][0]
    r = await ac.patch(f"/api/v1/hrm/payslips/{slip['id']}", headers=h, json={"bonus": 500, "other_deductions": 100})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["net"] < slip["net"] + 500 - 100
    too_much = await ac.patch(f"/api/v1/hrm/payslips/{slip['id']}", headers=h, json={"other_deductions": 999999})
    assert too_much.status_code == 422
    await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    await _even(ac, h)
    assert (await ac.patch(f"/api/v1/hrm/payslips/{slip['id']}", headers=h, json={"bonus": 1})).status_code == 409


@pytest.mark.asyncio
async def test_unpaid_leave_comes_off_the_month(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, basic=2200, allowances=0)
    leave = await ac.post(
        "/api/v1/hrm/leave", headers=h,
        json={"employee_id": person["id"], "leave_type": "unpaid", "starts_on": "2026-07-06", "ends_on": "2026-07-07"},
    )
    assert leave.status_code == 200, leave.text
    await ac.post(f"/api/v1/hrm/leave/{leave.json()['data']['id']}/decide", headers=h, json={"approve": True})
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-07"})).json()["data"]
    slip = run["slips"][0]
    assert slip["unpaid_days"] == 2 and slip["unpaid_deduction"] == 200 and slip["gross"] == 2000


@pytest.mark.asyncio
async def test_annual_leave_cannot_pass_the_allowance_or_overlap(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await ac.patch("/api/v1/hrm/settings", headers=h, json={"annual_leave_days": 5})
    person = await _person(ac, h)
    start = _next_monday(1)
    if start.year != (start + timedelta(days=30)).year:
        start = date(start.year + 1, 2, 2)
    body = {"employee_id": person["id"], "leave_type": "annual"}
    first = await ac.post(
        "/api/v1/hrm/leave", headers=h,
        json={**body, "starts_on": start.isoformat(), "ends_on": (start + timedelta(days=2)).isoformat()},
    )
    assert first.status_code == 200 and first.json()["data"]["days"] == 3
    overlap = await ac.post(
        "/api/v1/hrm/leave", headers=h, json={**body, "starts_on": start.isoformat(), "ends_on": start.isoformat()}
    )
    assert overlap.status_code == 409
    later = start + timedelta(days=7)
    too_long = await ac.post(
        "/api/v1/hrm/leave", headers=h,
        json={**body, "starts_on": later.isoformat(), "ends_on": (later + timedelta(days=4)).isoformat()},
    )
    assert too_long.status_code == 409 and "2 annual" in too_long.text


@pytest.mark.asyncio
async def test_turning_leave_down_needs_a_reason_and_decides_once(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h)
    start = _next_monday(2)
    row = (
        await ac.post(
            "/api/v1/hrm/leave", headers=h,
            json={"employee_id": person["id"], "leave_type": "sick", "starts_on": start.isoformat(), "ends_on": start.isoformat()},
        )
    ).json()["data"]
    url = f"/api/v1/hrm/leave/{row['id']}/decide"
    assert (await ac.post(url, headers=h, json={"approve": False})).status_code == 422
    assert (await ac.post(url, headers=h, json={"approve": False, "note": "Busy week"})).status_code == 200
    assert (await ac.post(url, headers=h, json={"approve": True})).status_code == 409


@pytest.mark.asyncio
async def test_nobody_decides_their_own_leave(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h, email="admin@alpha.example.com")
    start = _next_monday(3)
    row = (
        await ac.post(
            "/api/v1/hrm/leave", headers=h,
            json={"leave_type": "sick", "starts_on": start.isoformat(), "ends_on": start.isoformat()},
        )
    )
    assert row.status_code == 200, row.text
    r = await ac.post(f"/api/v1/hrm/leave/{row.json()['data']['id']}/decide", headers=h, json={"approve": True})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_staff_see_only_finished_payslips(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h, email="admin@alpha.example.com")
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-06"})).json()["data"]
    assert (await ac.get("/api/v1/hrm/me", headers=h)).json()["data"]["payslips"] == []
    await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    me = (await ac.get("/api/v1/hrm/me", headers=h)).json()["data"]
    assert len(me["payslips"]) == 1 and "basic_salary" not in me["employee"]


@pytest.mark.asyncio
async def test_someone_who_left_is_paid_their_last_month_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h)
    r = await ac.post(f"/api/v1/hrm/employees/{person['id']}/left", headers=h, json={"left_on": "2026-05-15", "reason": "Resigned"})
    assert r.status_code == 200, r.text
    may = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-05"})).json()["data"]
    assert len(may["slips"]) == 1
    june = await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-06"})
    assert june.status_code == 409


@pytest.mark.asyncio
async def test_attendance_saves_once_per_day_and_shows_leave(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h)
    today = date.today().isoformat()
    for status in ("late", "present"):
        r = await ac.post("/api/v1/hrm/attendance", headers=h, json={"day": today, "marks": [{"employee_id": person["id"], "status": status}]})
        assert r.status_code == 200, r.text
    rows = (await ac.get(f"/api/v1/hrm/attendance?day={today}", headers=h)).json()["data"]
    assert rows[0]["status"] == "present"
    future = (date.today() + timedelta(days=1)).isoformat()
    assert (await ac.post("/api/v1/hrm/attendance", headers=h, json={"day": future, "marks": [{"employee_id": person["id"], "status": "present"}]})).status_code == 422


@pytest.mark.asyncio
async def test_bad_paye_bands_are_refused(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    r = await ac.patch("/api/v1/hrm/settings", headers=h, json={"paye_bands": [{"width": 100, "rate": 0}]})
    assert r.status_code == 422


def test_each_role_has_its_own_job():
    from fastapi import HTTPException

    def can(role, area):
        try:
            hrm.job({"role": role}, area)
            return True
        except HTTPException:
            return False

    assert can("hrm_officer", "people") and can("hrm_officer", "leave") and not can("hrm_officer", "payroll")
    assert can("hrm_employee", "self") and not can("hrm_employee", "people")
    assert can("hrm_manager", "payroll")


@pytest.mark.asyncio
async def test_other_desks_are_shut_both_ways(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    assert (await ac.get("/api/v1/pos/sessions", headers=h)).status_code == 403
    await set_tenant_industry(db_session, seed["t1"], "gym")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    # Since 13 Nov every industry has HR on the one engine, but only its own HR areas:
    # a gym keeps staff, leave, time and pay, and does not get hiring.
    assert (await ac.get("/api/v1/hrm/summary", headers=h)).status_code == 200
    hiring = await ac.get("/api/v1/hrm/vacancies", headers=h)
    assert hiring.status_code == 403 and hiring.json()["detail"]["code"] == "HRM_AREA_OFF"


@pytest.mark.asyncio
async def test_one_company_cannot_see_anothers_staff(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    theirs = m.HrmEmployee(tenant_id=seed["t2"].id, employee_number="EMP-X", full_name="Theirs", hired_on=date.today(), status="active")
    db_session.add(theirs)
    await db_session.commit()
    r = await ac.patch(f"/api/v1/hrm/employees/{theirs.id}", headers=h, json={"job_title": "Hacked"})
    assert r.status_code == 404
    assert "Theirs" not in (await ac.get("/api/v1/hrm/employees", headers=h)).text
