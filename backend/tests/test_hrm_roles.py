"""Payroll officer, recruitment manager and auditor: what each may and may not do."""

from __future__ import annotations

import pytest

from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_people import _user

pytestmark = pytest.mark.asyncio
B = "/api/v1/hrm"


async def test_payroll_officer_draws_up_but_manager_approves(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h)
    po = await _user(ac, h, "payo@alpha.example.com", "hrm_payroll_officer")
    run = await ac.post(f"{B}/payroll", headers=po, json={"period": "2026-10"})
    assert run.status_code == 200, run.text
    assert run.json()["data"]["slips"][0]["gross"] == 3500  # sees pay
    rid = run.json()["data"]["id"]
    sid = run.json()["data"]["slips"][0]["id"]
    assert (await ac.patch(f"{B}/payslips/{sid}", headers=po, json={"bonus": 100})).status_code == 200
    appr = await ac.post(f"{B}/payroll/{rid}/approve", headers=po)
    assert appr.status_code == 403 and appr.json()["detail"]["code"] == "PAYROLL_APPROVER"
    assert (await ac.post(f"{B}/payroll/{rid}/pay", headers=po, json={"what": "staff", "method": "bank_transfer"})).status_code == 403
    # no hiring, cases or reviews
    assert (await ac.get(f"{B}/cases", headers=po)).status_code == 403
    assert (await ac.get(f"{B}/vacancies", headers=po)).status_code == 403
    assert (await ac.post(f"{B}/payroll/{rid}/approve", headers=h)).status_code == 200


async def test_recruiter_only_hires(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await ac.patch(f"{B}/settings", headers=h, json={"vacancy_approval": True})
    rec = await _user(ac, h, "rec@alpha.example.com", "hrm_recruiter")
    v = await ac.post(f"{B}/vacancies", headers=rec, json={"title": "Cashier", "department": "Sales", "openings": 1})
    assert v.status_code == 200, v.text
    assert v.json()["data"]["status"] == "pending"  # a recruiter proposes; an HR manager approves
    assert (await ac.get(f"{B}/payroll", headers=rec)).status_code == 403
    assert (await ac.get(f"{B}/cases", headers=rec)).status_code == 403
    assert (await ac.post(f"{B}/employees", headers=rec, json={"full_name": "Sneaky Hire", "hired_on": "2026-01-01", "basic_salary": 1, "allowances": 0})).status_code == 403


async def test_auditor_reads_but_never_writes(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h)
    run = (await ac.post(f"{B}/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    case = await ac.post(f"{B}/cases", headers=h, json={"employee_id": p["id"], "kind": "grievance", "subject": "Rota", "details": "Always nights"})
    assert case.status_code == 200
    au = await _user(ac, h, "audit@alpha.example.com", "hrm_auditor")
    assert (await ac.get(f"{B}/payroll", headers=au)).status_code == 200
    assert (await ac.get(f"{B}/employees", headers=au)).status_code == 200
    # confidential cases stay closed to the auditor
    assert (await ac.get(f"{B}/cases", headers=au)).status_code == 403
    assert (await ac.get(f"{B}/succession", headers=au)).status_code == 403
    # and nothing can be written or approved
    assert (await ac.post(f"{B}/payroll/{run['id']}/approve", headers=au)).status_code == 403
    assert (await ac.post(f"{B}/payroll", headers=au, json={"period": "2026-09"})).status_code == 403
    assert (await ac.post(f"{B}/employees", headers=au, json={"full_name": "Ghost", "hired_on": "2026-01-01", "basic_salary": 1, "allowances": 0})).status_code == 403
    assert (await ac.post(f"{B}/employees/{p['id']}/benefits", headers=au, json={"kind": "other", "name": "X1", "starts_on": "2026-01-01"})).status_code == 403
