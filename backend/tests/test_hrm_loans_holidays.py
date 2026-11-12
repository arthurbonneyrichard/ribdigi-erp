"""Staff loans and advances repaid through payroll, public holidays in leave, and the
two-person payroll rule."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app import hrm, hrm_loans
from app import models as m
from tests.conftest import auth_headers
from tests.test_hrm_desk import _admin, _even, _person

pytestmark = pytest.mark.asyncio


async def _second_manager(ac, h, seed):
    """Another HR manager, so one person can ask and another decide."""
    r = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": "hrlead@alpha.example.com", "full_name": "Efua Lead", "password": "SecurePass123!", "role": "hrm_manager"},
    )
    assert r.status_code == 200, r.text
    return await auth_headers(ac, email="hrlead@alpha.example.com", tenant_slug="alpha")


def _balance(accounts, code):
    return abs(accounts.get(code, 0.0))


async def _accounts(db_session, seed):
    rows = (await db_session.execute(select(m.Account).where(m.Account.tenant_id == seed["t1"].id))).scalars()
    return {row.code: float(row.balance or 0) for row in rows}


async def test_loan_is_decided_by_someone_else_paid_out_and_repaid_from_payroll(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    lead = await _second_manager(ac, h, seed)
    person = await _person(ac, h, basic=3000, allowances=0)
    asked = await ac.post(
        "/api/v1/hrm/loans", headers=h,
        json={"employee_id": person["id"], "kind": "loan", "principal": 900, "monthly_deduction": 400, "reason": "School fees"},
    )
    assert asked.status_code == 200, asked.text
    loan = asked.json()["data"]
    own = await ac.post(f"/api/v1/hrm/loans/{loan['id']}/decide", headers=h, json={"approve": True, "method": "cash"})
    assert own.status_code == 403
    ok = await ac.post(f"/api/v1/hrm/loans/{loan['id']}/decide", headers=lead, json={"approve": True, "method": "cash"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["status"] == "active"
    await _even(ac, h)

    for period, take, left in (("2026-09", 400, 500), ("2026-10", 400, 100), ("2026-11", 100, 0)):
        run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": period})).json()["data"]
        slip = run["slips"][0]
        assert slip["loan_deduction"] == take
        assert run["loan_deductions"] == take
        approved = await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
        assert approved.status_code == 200, approved.text
        row = (await ac.get("/api/v1/hrm/loans", headers=h)).json()["data"][0]
        assert row["balance"] == left
    assert row["status"] == "settled"
    assert _balance(await _accounts(db_session, seed), "1150") == 0
    await _even(ac, h)


async def test_loan_repayment_never_takes_pay_below_nil_and_cash_repays(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    lead = await _second_manager(ac, h, seed)
    person = await _person(ac, h, basic=500, allowances=0)
    loan = (
        await ac.post(
            "/api/v1/hrm/loans", headers=h,
            json={"employee_id": person["id"], "kind": "loan", "principal": 2000, "monthly_deduction": 2000},
        )
    ).json()["data"]
    await ac.post(f"/api/v1/hrm/loans/{loan['id']}/decide", headers=lead, json={"approve": True, "method": "bank_transfer"})
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    slip = run["slips"][0]
    assert slip["net"] == 0
    assert 0 < slip["loan_deduction"] < 2000
    paid = await ac.post(f"/api/v1/hrm/loans/{loan['id']}/repay", headers=h, json={"amount": 100, "method": "cash"})
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["balance"] == 1900
    too_much = await ac.post(f"/api/v1/hrm/loans/{loan['id']}/repay", headers=h, json={"amount": 5000, "method": "cash"})
    assert too_much.status_code == 422
    await _even(ac, h)


async def test_turning_down_needs_a_reason_and_advance_is_one_month(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    lead = await _second_manager(ac, h, seed)
    person = await _person(ac, h)
    bad = await ac.post(
        "/api/v1/hrm/loans", headers=h,
        json={"employee_id": person["id"], "kind": "advance", "principal": 500, "monthly_deduction": 250},
    )
    assert bad.status_code == 422
    adv = (
        await ac.post(
            "/api/v1/hrm/loans", headers=h,
            json={"employee_id": person["id"], "kind": "advance", "principal": 500, "monthly_deduction": 500},
        )
    ).json()["data"]
    no_reason = await ac.post(f"/api/v1/hrm/loans/{adv['id']}/decide", headers=lead, json={"approve": False})
    assert no_reason.status_code == 422
    no = await ac.post(f"/api/v1/hrm/loans/{adv['id']}/decide", headers=lead, json={"approve": False, "note": "Ask next month"})
    assert no.json()["data"]["status"] == "rejected"


async def test_holidays_are_not_leave_days(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h)
    # 2027-03-01 is a Monday; Saturday 6 March is Independence Day, so the Friday is entered as the holiday.
    added = await ac.post(
        "/api/v1/hrm/holidays", headers=h, json={"holidays": [{"day": "2027-03-05", "name": "Independence Day (observed)"}]}
    )
    assert added.status_code == 200, added.text
    leave = await ac.post(
        "/api/v1/hrm/leave", headers=h,
        json={"employee_id": person["id"], "leave_type": "annual", "starts_on": "2027-03-01", "ends_on": "2027-03-05"},
    )
    assert leave.status_code == 200, leave.text
    assert leave.json()["data"]["days"] == 4
    only_holiday = await ac.post(
        "/api/v1/hrm/leave", headers=h,
        json={"employee_id": person["id"], "leave_type": "sick", "starts_on": "2027-03-05", "ends_on": "2027-03-07"},
    )
    assert only_holiday.status_code in (409, 422)


def test_suggested_holidays_compute_easter_and_farmers_day():
    days = {row["name"]: row["day"] for row in hrm_loans.suggested_ghana_holidays(2027)}
    assert days["Good Friday"] == "2027-03-26"
    assert days["Easter Monday"] == "2027-03-29"
    assert days["Farmers' Day"] == "2027-12-03"
    assert hrm.working_days(date(2027, 3, 1), date(2027, 3, 5), {date(2027, 3, 5)}) == 4


async def test_two_person_payroll(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    lead = await _second_manager(ac, h, seed)
    await _person(ac, h)
    assert (await ac.patch("/api/v1/hrm/settings", headers=h, json={"two_person_payroll": True})).status_code == 200
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    same = await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    assert same.status_code == 403
    assert same.json()["detail"]["code"] == "PAYROLL_SECOND_PERSON"
    other = await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=lead)
    assert other.status_code == 200, other.text


async def test_staff_ask_for_their_own_advance(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, email="yaa.staff@alpha.example.com")
    made = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": "yaa.staff@alpha.example.com", "full_name": "Yaa Staff", "password": "SecurePass123!", "role": "hrm_employee"},
    )
    assert made.status_code == 200, made.text
    staff = await auth_headers(ac, email="yaa.staff@alpha.example.com", tenant_slug="alpha")
    asked = await ac.post(
        "/api/v1/hrm/me/loans", headers=staff,
        json={"kind": "advance", "principal": 300, "monthly_deduction": 300, "reason": "Rent due"},
    )
    assert asked.status_code == 200, asked.text
    assert asked.json()["data"]["employee_id"] == person["id"]
    listed = await ac.get("/api/v1/hrm/loans", headers=staff)
    assert listed.status_code == 403
    mine = (await ac.get("/api/v1/hrm/me", headers=staff)).json()["data"]
    assert len(mine["loans"]) == 1
