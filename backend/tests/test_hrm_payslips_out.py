"""Payslips leaving the system: PDF, email to staff, and the salary payment file.

Also the SSNIT-exempt and senior-staff marks, and the bonus allowance worked out from the
year's real basic salary rather than this month's basic x 12."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.emailer import clear_dev_outbox, get_dev_outbox
from app.hrm_payroll import PayslipInput, StatutoryRates, compute_payslip
from tests.conftest import auth_headers
from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_payroll_engine import rates

pytestmark = pytest.mark.asyncio


async def _approved_run(ac, h, period="2026-06"):
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": period})).json()["data"]
    r = await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def test_payslip_pdf_for_hr_and_only_own_for_staff(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    made = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": "emp@alpha.example.com", "full_name": "Emp", "password": "SecurePass123!", "role": "hrm_employee"},
    )
    assert made.status_code == 200, made.text
    staff = await auth_headers(ac, email="emp@alpha.example.com", tenant_slug="alpha")
    mine = await _person(ac, h, email="emp@alpha.example.com", bank_account="0011223344")
    other = await _person(ac, h)

    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-06"})).json()["data"]
    my_slip = next(s for s in run["slips"] if s["employee_id"] == mine["id"])
    other_slip = next(s for s in run["slips"] if s["employee_id"] == other["id"])
    # Draft: HR can look, staff cannot.
    assert (await ac.get(f"/api/v1/hrm/payslips/{my_slip['id']}/pdf", headers=staff)).status_code == 404
    hr = await ac.get(f"/api/v1/hrm/payslips/{my_slip['id']}/pdf", headers=h)
    assert hr.status_code == 200 and hr.content.startswith(b"%PDF")
    assert hr.headers["cache-control"] == "no-store"

    await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    own = await ac.get(f"/api/v1/hrm/payslips/{my_slip['id']}/pdf", headers=staff)
    assert own.status_code == 200 and own.content.startswith(b"%PDF")
    assert b"0011223344" not in own.content  # account number masked
    assert (await ac.get(f"/api/v1/hrm/payslips/{other_slip['id']}/pdf", headers=staff)).status_code == 404
    # Staff cannot email or make payment files.
    assert (await ac.post(f"/api/v1/hrm/payroll/{run['id']}/email-payslips", headers=staff, json={})).status_code == 403
    assert (await ac.get(f"/api/v1/hrm/payroll/{run['id']}/payment-file", headers=staff)).status_code == 403


async def test_email_payslips_attaches_pdf_skips_no_email_and_sends_once(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h, email="ama@example.com")
    await _person(ac, h)  # no email
    draft = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-06"})).json()["data"]
    assert (await ac.post(f"/api/v1/hrm/payroll/{draft['id']}/email-payslips", headers=h, json={})).status_code == 409
    await ac.post(f"/api/v1/hrm/payroll/{draft['id']}/approve", headers=h)

    clear_dev_outbox()
    r = await ac.post(f"/api/v1/hrm/payroll/{draft['id']}/email-payslips", headers=h, json={})
    assert r.status_code == 200, r.text
    out = r.json()["data"]
    assert out["sent"] == 1 and len(out["no_email"]) == 1 and out["failed"] == []
    mail = get_dev_outbox()[-1]
    assert "ama@example.com" in str(mail.get("to") or mail.get("recipients"))
    assert any(a["filename"].endswith(".pdf") for a in mail.get("attachments") or [])
    # No pay figures in the body.
    assert "Net" not in (mail.get("text_body") or mail.get("text") or "")

    again = (await ac.post(f"/api/v1/hrm/payroll/{draft['id']}/email-payslips", headers=h, json={})).json()["data"]
    assert again["sent"] == 0 and again["already_sent"] == 1
    resent = (await ac.post(f"/api/v1/hrm/payroll/{draft['id']}/email-payslips", headers=h, json={"resend": True})).json()["data"]
    assert resent["sent"] == 1
    runs = (await ac.get("/api/v1/hrm/payroll", headers=h)).json()["data"]
    slips = next(x for x in runs if x["id"] == draft["id"])["slips"]
    assert sum(1 for s in slips if s["emailed_at"]) == 1


async def test_payment_files_bank_and_mobile_money(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h, bank_name="GCB", bank_account="1234567890")
    await _person(ac, h, mobile_money="+233241112222")
    run = await _approved_run(ac, h)

    bank = await ac.get(f"/api/v1/hrm/payroll/{run['id']}/payment-file?method=bank", headers=h)
    assert bank.status_code == 200 and bank.headers["content-type"].startswith("text/csv")
    lines = bank.text.strip().splitlines()
    assert lines[0].startswith("Employee number,Name,Bank,Account number,Amount")
    assert len(lines) == 2 and "1234567890" in lines[1] and "Salary 2026-06" in lines[1]
    assert bank.headers["x-rows"] == "1" and bank.headers["x-left-out"] == "1"

    momo = await ac.get(f"/api/v1/hrm/payroll/{run['id']}/payment-file?method=mobile_money", headers=h)
    rows = momo.text.strip().splitlines()
    # A leading + is quoted so a spreadsheet does not read it as a formula.
    assert len(rows) == 2 and "'+233241112222" in rows[1]
    assert (await ac.get(f"/api/v1/hrm/payroll/{run['id']}/payment-file?method=cash", headers=h)).status_code == 422


async def test_paye_schedule_has_gra_return_columns(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h, basic=3000, allowances=500, tin="P0012345678")
    await _approved_run(ac, h)
    data = (await ac.get("/api/v1/hrm/reports/paye?period=2026-06", headers=h)).json()["data"]
    row = data["rows"][0]
    for key in ("basic", "cash_allowances", "bonus", "bonus_tax", "excess_bonus", "taxable", "tax_on_chargeable", "overtime", "overtime_tax", "paye", "residence"):
        assert key in row, key
    assert row["basic"] == 3000 and row["cash_allowances"] == 500 and row["residence"] == "resident"
    assert row["tax_on_chargeable"] == row["paye"]
    assert data["totals"]["basic"] == 3000


def test_ssnit_exempt_and_senior_staff_in_the_engine():
    r: StatutoryRates = rates(overtime_junior_cap=Decimal("1500"))
    exempt = compute_payslip(PayslipInput(basic=Decimal("5000"), ssnit_exempt=True), r)
    assert exempt.ssnit_employee == 0 and exempt.ssnit_employer == 0 and exempt.taxable == Decimal("5000")
    junior = compute_payslip(PayslipInput(basic=Decimal("1200"), overtime=Decimal("800")), r)
    senior = compute_payslip(PayslipInput(basic=Decimal("1200"), overtime=Decimal("800"), senior_staff=True), r)
    assert junior.overtime_tax == Decimal("50.00") and senior.overtime_tax == 0


async def test_flags_on_the_record_reach_the_payslip(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, basic=4000, allowances=0, ssnit_exempt=True)
    assert person["ssnit_exempt"] is True and person["senior_staff"] is False
    r = await ac.patch(f"/api/v1/hrm/employees/{person['id']}", headers=h, json={"senior_staff": True})
    assert r.status_code == 200 and r.json()["data"]["senior_staff"] is True
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-06"})).json()["data"]
    slip = next(s for s in run["slips"] if s["employee_id"] == person["id"])
    assert slip["ssnit_employee"] == 0 and slip["ssnit_exempt"] is True and slip["senior_staff"] is True


async def test_bonus_allowance_uses_the_year_actually_employed(client, db_session):
    """Hired 1 Jul 2026 on 2,000: annual basic is 6 x 2,000 = 12,000, allowance 1,800 (not 3,600)."""
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, basic=2000, allowances=0, hired_on="2026-07-01")
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-07"})).json()["data"]
    slip = next(s for s in run["slips"] if s["employee_id"] == person["id"])
    r = await ac.patch(f"/api/v1/hrm/payslips/{slip['id']}", headers=h, json={"bonus": 3000, "other_deductions": 0})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["bonus_concessional"] == 1800
