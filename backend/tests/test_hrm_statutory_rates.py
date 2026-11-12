"""Dated PAYE / SSNIT / pension rates: payroll uses the month's row, Tier 2 and Tier 3
are booked and paid on their own, and an approved month's rates cannot be rewritten."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from tests.test_hrm_desk import _admin, _even, _person

pytestmark = pytest.mark.asyncio

BANDS = [
    {"width": 490, "rate": 0},
    {"width": 110, "rate": 5},
    {"width": 130, "rate": 10},
    {"width": 3166.67, "rate": 17.5},
    {"width": 16000, "rate": 25},
    {"width": 30520, "rate": 30},
    {"width": None, "rate": 35},
]


def _rate(effective_from: str, **extra) -> dict:
    body = {
        "effective_from": effective_from,
        "employee_percent": 5.5,
        "employer_percent": 13,
        "tier2_percent": 5,
        "insurable_cap": 10000,
        "paye_bands": BANDS,
        "source_note": "Test rates, not checked against GRA",
    }
    body.update(extra)
    return body


async def test_month_uses_its_dated_rates_with_tiers(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    added = await ac.post("/api/v1/hrm/statutory-rates", headers=h, json=_rate("2026-01-01"))
    assert added.status_code == 200, added.text
    await _person(ac, h, basic=12000, allowances=0, tier3_percent=3)
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    slip = run["slips"][0]
    # Same figures as the hand-worked engine test: cap 10,000, Tier 2 5%, Tier 3 3%.
    assert (slip["ssnit_employee"], slip["ssnit_employer"]) == (550, 1300)
    assert (slip["tier1"], slip["tier2"], slip["tier3"]) == (1350, 500, 360)
    assert slip["paye"] == 2371 and slip["net"] == 8719
    assert slip["rates_used"]["tier2_percent"] == "5.000" or slip["rates_used"]["tier2_percent"].startswith("5")
    assert run["tier2"] == 500 and run["tier3"] == 360 and run["ssnit_due"] == 1350

    approved = await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    assert approved.status_code == 200, approved.text
    await _even(ac, h)
    accounts = {
        row.code: float(row.balance or 0)
        for row in (
            await db_session.execute(select(m.Account).where(m.Account.tenant_id == seed["t1"].id))
        ).scalars()
    }
    assert accounts.get("2192") in (500.0, -500.0)
    assert accounts.get("2195") in (360.0, -360.0)

    url = f"/api/v1/hrm/payroll/{run['id']}/pay"
    for what in ("staff", "paye", "ssnit", "tier2"):
        r = await ac.post(url, headers=h, json={"what": what, "method": "bank_transfer"})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] != "paid"
    last = await ac.post(url, headers=h, json={"what": "tier3", "method": "bank_transfer"})
    assert last.json()["data"]["status"] == "paid"
    again = await ac.post(url, headers=h, json={"what": "tier2", "method": "bank_transfer"})
    assert again.status_code == 409
    await _even(ac, h)


async def test_used_rates_are_locked_and_history_cannot_be_rewritten(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    rate = (await ac.post("/api/v1/hrm/statutory-rates", headers=h, json=_rate("2026-01-01"))).json()["data"]
    await _person(ac, h)
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    assert (await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)).status_code == 200

    gone = await ac.delete(f"/api/v1/hrm/statutory-rates/{rate['id']}", headers=h)
    assert gone.status_code == 409
    backdated = await ac.post("/api/v1/hrm/statutory-rates", headers=h, json=_rate("2026-10-15"))
    assert backdated.status_code == 409
    later = await ac.post("/api/v1/hrm/statutory-rates", headers=h, json=_rate("2026-11-01", tier2_percent=0))
    assert later.status_code == 200, later.text
    listed = (await ac.get("/api/v1/hrm/statutory-rates", headers=h)).json()["data"]
    by_id = {row["id"]: row for row in listed}
    assert by_id[rate["id"]]["locked"] is True
    assert by_id[later.json()["data"]["id"]]["locked"] is False
    # The unused future row can be removed.
    assert (await ac.delete(f"/api/v1/hrm/statutory-rates/{later.json()['data']['id']}", headers=h)).status_code == 200


async def test_bad_rates_are_refused(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    closed = await ac.post(
        "/api/v1/hrm/statutory-rates", headers=h, json=_rate("2026-01-01", paye_bands=[{"width": 100, "rate": 0}])
    )
    assert closed.status_code == 422
    tier2_too_big = await ac.post("/api/v1/hrm/statutory-rates", headers=h, json=_rate("2026-01-01", tier2_percent=30))
    assert tier2_too_big.status_code == 422
    bad_card = await ac.post(
        "/api/v1/hrm/employees", headers=h,
        json={"full_name": "Kofi Mensah", "hired_on": "2024-01-15", "ghana_card": "12345"},
    )
    assert bad_card.status_code == 422


async def test_without_dated_rates_payroll_is_unchanged(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h, basic=3000, allowances=500)
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    slip = run["slips"][0]
    assert slip["ssnit_employee"] == 165 and slip["tier2"] == 0 and slip["tier3"] == 0
    assert slip["rates_used"]["rate_id"] is None
    assert run["statutory_rate_id"] is None


async def test_minimum_wage_blocks_approval_until_pay_is_fixed(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    assert (await ac.post("/api/v1/hrm/statutory-rates", headers=h, json=_rate("2026-01-01", minimum_daily_wage=20, overtime_junior_cap=1500))).status_code == 200
    low = await _person(ac, h, basic=300, allowances=0)
    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-02"})).json()["data"]
    slip = next(s for s in run["slips"] if s["employee_id"] == low["id"])
    assert slip["warnings"] == ["below_minimum_wage"]
    blocked = await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "BELOW_MINIMUM_WAGE"
    rates = (await ac.get("/api/v1/hrm/statutory-rates", headers=h)).json()["data"]
    assert rates[0]["minimum_daily_wage"] == 20 and rates[0]["overtime_junior_cap"] == 1500
