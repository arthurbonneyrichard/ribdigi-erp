"""Salary changes from a date, back pay for approved months, corrections, and the
PAYE / SSNIT schedules and yearly tax statement read from approved payslips."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers
from tests.test_hrm_desk import _admin, _even, _person

pytestmark = pytest.mark.asyncio


async def _run(ac, h, period):
    r = await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": period})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _approve(ac, h, run):
    r = await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    assert r.status_code == 200, r.text


async def test_future_change_is_used_from_its_month(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, basic=2000, allowances=0, tin="P0011223344")
    r = await ac.post(
        f"/api/v1/hrm/employees/{person['id']}/salary", headers=h,
        json={"effective_from": "2099-03-01", "basic_salary": 2500, "reason": "Promotion to supervisor"},
    )
    assert r.status_code == 200, r.text
    feb = await _run(ac, h, "2099-02")
    mar = await _run(ac, h, "2099-03")
    assert feb["slips"][0]["basic"] == 2000
    assert mar["slips"][0]["basic"] == 2500
    history = (await ac.get(f"/api/v1/hrm/employees/{person['id']}/salary", headers=h)).json()["data"]
    assert history[0]["reason"] == "Promotion to supervisor"


async def test_backdated_raise_pays_arrears_next_month_and_never_edits_approved(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, basic=2000, allowances=100)
    sep = await _run(ac, h, "2026-09")
    await _approve(ac, h, sep)
    oct_ = await _run(ac, h, "2026-10")
    await _approve(ac, h, oct_)
    raised = await ac.post(
        f"/api/v1/hrm/employees/{person['id']}/salary", headers=h,
        json={"effective_from": "2026-09-01", "basic_salary": 2300, "allowances": 150, "reason": "Pay review agreed late"},
    )
    assert raised.status_code == 200, raised.text
    adjustments = raised.json()["data"]["adjustments"]
    assert sorted(a["for_period"] for a in adjustments) == ["2026-09", "2026-09", "2026-10", "2026-10"]
    # September as approved still shows the old basic.
    runs = {r["period"]: r for r in (await ac.get("/api/v1/hrm/payroll", headers=h)).json()["data"]}
    assert runs["2026-09"]["gross"] == sep["gross"]

    nov = await _run(ac, h, "2026-11")
    slip = nov["slips"][0]
    assert slip["basic"] == 2300
    assert slip["arrears_basic"] == 600  # 300 back pay for each of two months
    assert slip["adjustment"] == 100  # 50 allowance for each of two months
    assert slip["gross"] == 2300 + 150 + 600 + 100
    assert slip["ssnit_employee"] == round((2300 + 600) * 0.055, 2)
    await _approve(ac, h, nov)
    left = [a for a in (await ac.get("/api/v1/hrm/adjustments", headers=h)).json()["data"] if a["status"] != "applied"]
    assert left == []
    await _even(ac, h)


async def test_thrown_away_draft_gives_corrections_back(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, basic=2000, allowances=0)
    fix = await ac.post(
        "/api/v1/hrm/adjustments", headers=h,
        json={"employee_id": person["id"], "kind": "correction", "amount": -150, "reason": "Overtime paid twice in August"},
    )
    assert fix.status_code == 200, fix.text
    draft = await _run(ac, h, "2026-10")
    assert draft["slips"][0]["adjustment"] == -150
    assert (await ac.delete(f"/api/v1/hrm/payroll/{draft['id']}", headers=h)).status_code == 200
    rows = (await ac.get("/api/v1/hrm/adjustments", headers=h)).json()["data"]
    assert rows[0]["status"] == "pending"
    again = await _run(ac, h, "2026-10")
    assert again["slips"][0]["adjustment"] == -150
    gone = await ac.delete(f"/api/v1/hrm/adjustments/{rows[0]['id']}", headers=h)
    assert gone.status_code == 409  # on a draft now: cancel by throwing the draft away first


async def test_paye_ssnit_schedules_and_tax_statement(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, basic=3000, allowances=500, tin="P0099887766", ssnit_number="C123456789012", email="kwesi@alpha.example.com")
    nobody = await _person(ac, h, basic=1000, allowances=0)
    for period in ("2026-09", "2026-10"):
        await _approve(ac, h, await _run(ac, h, period))
    paye = (await ac.get("/api/v1/hrm/reports/paye?period=2026-10", headers=h)).json()["data"]
    mine = next(r for r in paye["rows"] if r["tin"] == "P0099887766")
    assert mine["gross"] == 3500 and mine["taxable"] == 3335
    assert nobody["full_name"] in paye["missing_tax_id"]
    ssnit = (await ac.get("/api/v1/hrm/reports/ssnit?period=2026-10", headers=h)).json()["data"]
    row = next(r for r in ssnit["rows"] if r["ssnit_number"] == "C123456789012")
    assert (row["insurable"], row["employee_share"], row["employer_share"]) == (3000, 165, 390)
    assert nobody["full_name"] in ssnit["missing_ssnit_number"]

    year = (await ac.get(f"/api/v1/hrm/reports/tax-statement?employee_id={person['id']}&year=2026", headers=h)).json()["data"]
    assert [m["period"] for m in year["months"]] == ["2026-09", "2026-10"]
    assert year["totals"]["paye"] == round(2 * mine["paye"], 2)

    made = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": "kwesi@alpha.example.com", "full_name": "Kwesi", "password": "SecurePass123!", "role": "hrm_employee"},
    )
    assert made.status_code == 200, made.text
    staff = await auth_headers(ac, email="kwesi@alpha.example.com", tenant_slug="alpha")
    own = await ac.get("/api/v1/hrm/me/tax-statement?year=2026", headers=staff)
    assert own.status_code == 200 and own.json()["data"]["totals"]["paye"] == year["totals"]["paye"]
    other = await ac.get(f"/api/v1/hrm/reports/tax-statement?employee_id={nobody['id']}&year=2026", headers=staff)
    assert other.status_code == 403
