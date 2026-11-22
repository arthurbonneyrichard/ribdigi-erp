"""Payroll and HR security: who may reach pay, other companies, approved runs, double posting."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import models as m
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_people import _user

pytestmark = pytest.mark.asyncio
B = "/api/v1/hrm"


async def _beta_admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t2"], "hrm")
    db_session.add(m.User(tenant_id=seed["t2"].id, email="admin@beta.example.com", full_name="Beta Admin",
                          password_hash=hash_password("SecurePass123!"), role="company_admin", email_verified=True))
    await db_session.commit()
    return await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")


async def test_pay_is_closed_to_officers_and_staff(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h, email="pay1@alpha.example.com")
    run = (await ac.post(f"{B}/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    slip = run["slips"][0]["id"]
    for who in (await _user(ac, h, "off9@alpha.example.com", "hrm_officer"), await _user(ac, h, "pay1@alpha.example.com", "hrm_employee")):
        assert (await ac.get(f"{B}/payroll", headers=who)).status_code == 403
        assert (await ac.post(f"{B}/payroll", headers=who, json={"period": "2026-09"})).status_code == 403
        assert (await ac.post(f"{B}/payroll/{run['id']}/approve", headers=who)).status_code == 403
        assert (await ac.post(f"{B}/payroll/{run['id']}/pay", headers=who, json={})).status_code in (403, 422)
        assert (await ac.patch(f"{B}/payslips/{slip}", headers=who, json={"bonus": 99999})).status_code == 403
        assert (await ac.get(f"{B}/employees/{p['id']}/salary", headers=who)).status_code == 403
        assert (await ac.get(f"{B}/payroll/{run['id']}/payment-file", headers=who)).status_code == 403


async def test_other_company_cannot_reach_payroll(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h)
    run = (await ac.post(f"{B}/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    slip = run["slips"][0]["id"]
    beta = await _beta_admin(ac, seed, db_session)
    assert (await ac.get(f"{B}/payroll", headers=beta)).json()["data"] == []
    assert (await ac.post(f"{B}/payroll/{run['id']}/approve", headers=beta)).status_code == 404
    assert (await ac.delete(f"{B}/payroll/{run['id']}", headers=beta)).status_code == 404
    assert (await ac.patch(f"{B}/payslips/{slip}", headers=beta, json={"bonus": 5})).status_code == 404
    assert (await ac.get(f"{B}/payslips/{slip}/pdf", headers=beta)).status_code == 404
    # a salary history is tenant-filtered: another company sees nothing, and cannot add to it
    ch = await ac.post(f"{B}/employees/{p['id']}/salary", headers=h, json={"effective_from": "2026-11-01", "basic_salary": 4000, "allowances": 500, "reason": "Annual review"})
    assert ch.status_code == 200, ch.text
    assert (await ac.get(f"{B}/employees/{p['id']}/salary", headers=beta)).json()["data"] == []
    assert (await ac.post(f"{B}/employees/{p['id']}/salary", headers=beta, json={"effective_from": "2026-12-01", "basic_salary": 1, "allowances": 0, "reason": "Spy change"})).status_code in (403, 404)
    # and the run is untouched
    assert (await ac.get(f"{B}/payroll", headers=h)).json()["data"][0]["status"] == "draft"


async def test_approved_payroll_is_frozen_and_posts_once(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h)
    run = (await ac.post(f"{B}/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    slip = run["slips"][0]["id"]
    assert (await ac.post(f"{B}/payroll/{run['id']}/approve", headers=h)).status_code == 200

    async def journals():
        return (await db_session.execute(select(func.count()).select_from(m.JournalEntry).where(m.JournalEntry.tenant_id == seed["t1"].id))).scalar_one()

    before = await journals()
    for _ in range(2):
        assert (await ac.post(f"{B}/payroll/{run['id']}/approve", headers=h)).status_code == 409
    assert await journals() == before
    assert (await ac.patch(f"{B}/payslips/{slip}", headers=h, json={"bonus": 500})).status_code == 409
    assert (await ac.delete(f"{B}/payroll/{run['id']}", headers=h)).status_code == 409
    assert (await ac.post(f"{B}/payroll", headers=h, json={"period": "2026-10"})).status_code == 409
