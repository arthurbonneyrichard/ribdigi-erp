"""Only someone with pay rights can change pay or the numbers pay is sent to.

An HR officer or desk manager could otherwise change a colleague's bank or Mobile Money
number and redirect their salary without ever seeing it."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers
from tests.test_hrm_desk import _admin, _person

pytestmark = pytest.mark.asyncio


async def test_officer_cannot_redirect_pay(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    made = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": "officer@alpha.example.com", "full_name": "Officer", "password": "SecurePass123!", "role": "hrm_officer"},
    )
    assert made.status_code == 200, made.text
    officer = await auth_headers(ac, email="officer@alpha.example.com", tenant_slug="alpha")
    person = await _person(ac, h, mobile_money="+233241111111", bank_account="111")

    for field, value in (("mobile_money", "+233249999999"), ("bank_account", "999"), ("ghana_card", None), ("basic_salary", 9000)):
        r = await ac.patch(f"/api/v1/hrm/employees/{person['id']}", headers=officer, json={field: value})
        assert r.status_code == 403, (field, r.text)
    ok = await ac.patch(f"/api/v1/hrm/employees/{person['id']}", headers=officer, json={"job_title": "Supervisor", "phone": "+233200000001"})
    assert ok.status_code == 200, ok.text
    assert "bank_account" not in ok.json()["data"]

    # Adding someone: ID and contact numbers are fine, pay amounts are not.
    added = await ac.post(
        "/api/v1/hrm/employees", headers=officer,
        json={"full_name": "New Starter", "hired_on": "2026-01-05", "ghana_card": "GHA-123456789-0", "mobile_money": "+233241234567"},
    )
    assert added.status_code == 200, added.text
    paid = await ac.post("/api/v1/hrm/employees", headers=officer, json={"full_name": "Paid Starter", "hired_on": "2026-01-05", "basic_salary": 3000})
    assert paid.status_code == 403

    # The HR manager / company admin can.
    boss = await ac.patch(f"/api/v1/hrm/employees/{person['id']}", headers=h, json={"mobile_money": "+233249999999"})
    assert boss.status_code == 200 and boss.json()["data"]["mobile_money"] == "+233249999999"
