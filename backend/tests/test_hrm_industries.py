"""HR in every industry on the one HR engine: each business type gets its own HR areas,
desk staff see only their own file, desk managers run people admin without pay, and a
company's HR rows stay its own."""

from __future__ import annotations

import pytest

from app import hrm
from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio


async def _company(ac, seed, db_session, industry):
    await set_tenant_industry(db_session, seed["t1"], industry)
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _user(ac, h, email, role):
    r = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": email, "full_name": email.split("@")[0].title(), "password": "SecurePass123!", "role": role},
    )
    assert r.status_code == 200, r.text
    return await auth_headers(ac, email=email, tenant_slug="alpha")


async def _staff_record(ac, h, email, basic=2000):
    r = await ac.post(
        "/api/v1/hrm/employees", headers=h,
        json={"full_name": email.split("@")[0].title(), "email": email, "hired_on": "2024-01-15", "basic_salary": basic},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_each_industry_has_its_hr_areas():
    assert hrm.hr_areas_for("hrm") == hrm.ALL_HR_AREAS
    assert hrm.hr_areas_for("fmcg") == hrm.ALL_HR_AREAS
    assert "payroll" in hrm.hr_areas_for("retail") and "recruitment" not in hrm.hr_areas_for("retail")
    assert "training" in hrm.hr_areas_for("pharmacy") and "contracts" in hrm.hr_areas_for("hotel")
    assert hrm.hr_areas_for(None) == frozenset({"self"})


async def test_retail_company_runs_payroll_and_cashier_sees_only_own_file(client, db_session):
    ac, seed = client
    h = await _company(ac, seed, db_session, "retail")
    await _staff_record(ac, h, "till@alpha.example.com")
    run = await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})
    assert run.status_code == 200, run.text
    cashier = await _user(ac, h, "till@alpha.example.com", "cashier")
    assert (await ac.get("/api/v1/hrm/employees", headers=cashier)).status_code == 403
    assert (await ac.get("/api/v1/hrm/payroll", headers=cashier)).status_code == 403
    assert (await ac.get("/api/v1/hrm/me", headers=cashier)).status_code == 200
    asked = await ac.post(
        "/api/v1/hrm/leave", headers=cashier, json={"leave_type": "annual", "starts_on": "2027-02-01", "ends_on": "2027-02-02"}
    )
    assert asked.status_code == 200, asked.text
    # A cashier cannot decide leave, not even someone else's.
    assert (await ac.post(f"/api/v1/hrm/leave/{asked.json()['data']['id']}/decide", headers=cashier, json={"approve": True})).status_code == 403
    # Hiring is not part of retail HR.
    off = await ac.get("/api/v1/hrm/vacancies", headers=h)
    assert off.status_code == 403 and off.json()["detail"]["code"] == "HRM_AREA_OFF"


async def test_restaurant_manager_runs_people_admin_not_pay_and_waiter_clocks_in(client, db_session):
    ac, seed = client
    h = await _company(ac, seed, db_session, "restaurant")
    await _staff_record(ac, h, "waiter@alpha.example.com")
    manager = await _user(ac, h, "chef.boss@alpha.example.com", "restaurant_manager")
    waiter = await _user(ac, h, "waiter@alpha.example.com", "restaurant_waiter")
    people = await ac.get("/api/v1/hrm/employees", headers=manager)
    assert people.status_code == 200
    assert "basic_salary" not in people.json()["data"][0]
    assert (await ac.get("/api/v1/hrm/payroll", headers=manager)).status_code == 403
    assert (await ac.get("/api/v1/hrm/time/day?day=2026-11-02", headers=manager)).status_code == 200
    punch = await ac.post("/api/v1/hrm/me/clock", headers=waiter, json={"kind": "in"})
    assert punch.status_code == 200, punch.text
    assert (await ac.get("/api/v1/hrm/time/day?day=2026-11-02", headers=waiter)).status_code == 403


async def test_hrm_desk_roles_stay_on_the_hrm_desk(client, db_session):
    ac, seed = client
    h = await _company(ac, seed, db_session, "retail")
    made = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": "hrofficer@alpha.example.com", "full_name": "Officer", "password": "SecurePass123!", "role": "hrm_officer"},
    )
    assert made.status_code in (400, 403, 409, 422), made.text
