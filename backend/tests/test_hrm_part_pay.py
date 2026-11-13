"""Weekly pay on a monthly payroll: part-payments during the month, taken back in full by the
month's payroll after PAYE and SSNIT on the whole month."""

from __future__ import annotations

import pytest

from tests.test_hrm_desk import _admin, _even, _person

pytestmark = pytest.mark.asyncio


async def test_weekly_part_payments_come_off_the_month(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    weekly = await _person(ac, h, basic=2600, allowances=0, pay_frequency="weekly")
    monthly = await _person(ac, h, basic=3000, allowances=0)

    sheet = (await ac.get("/api/v1/hrm/part-pay?paid_on=2026-04-03", headers=h)).json()["data"]
    row = next(p for p in sheet["people"] if p["employee_id"] == weekly["id"])
    assert row["suggested"] == 480  # 2,600 × 12 ÷ 52 × 80%
    assert all(p["employee_id"] != monthly["id"] for p in sheet["people"])

    for day in ("2026-04-03", "2026-04-10"):
        paid = await ac.post("/api/v1/hrm/part-pay", headers=h, json={"paid_on": day, "method": "cash", "lines": [{"employee_id": weekly["id"], "amount": 480}]})
        assert paid.status_code == 200, paid.text
    again = await ac.post("/api/v1/hrm/part-pay", headers=h, json={"paid_on": "2026-04-10", "method": "cash", "lines": [{"employee_id": weekly["id"], "amount": 480}]})
    assert again.status_code == 409
    no = await ac.post("/api/v1/hrm/part-pay", headers=h, json={"paid_on": "2026-04-10", "method": "cash", "lines": [{"employee_id": monthly["id"], "amount": 100}]})
    assert no.status_code == 422

    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-04"})).json()["data"]
    slip = next(s for s in run["slips"] if s["employee_id"] == weekly["id"])
    assert slip["gross"] == 2600 and slip["ssnit_employee"] == 143  # SSNIT on the whole month
    assert slip["part_paid"] == 960 and slip["loan_deduction"] == 960
    assert round(slip["net"], 2) == round(2600 - 143 - slip["paye"] - 960, 2)
    late = await ac.post("/api/v1/hrm/part-pay", headers=h, json={"paid_on": "2026-04-24", "method": "cash", "lines": [{"employee_id": weekly["id"], "amount": 480}]})
    assert late.status_code == 409
    assert (await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)).status_code == 200
    loans = (await ac.get("/api/v1/hrm/loans", headers=h)).json()["data"]
    assert {l["status"] for l in loans if l["kind"] == "part_pay"} == {"settled"}
    await _even(ac, h)
