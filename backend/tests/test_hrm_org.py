"""Org chart from "Reports to", and headcount planned / filled / being hired by department."""

from __future__ import annotations

import pytest

from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_leave_steps import _login_staff

pytestmark = pytest.mark.asyncio


async def test_org_chart_and_headcount(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    boss = await _person(ac, h, full_name="Ama Boss", department="Sales")
    await _person(ac, h, full_name="Kojo Rep", department="Sales", manager_id=boss["id"])
    await _person(ac, h, full_name="Esi Rep", department="Sales", manager_id=boss["id"], email="esi@alpha.example.com")
    await _person(ac, h, full_name="Yaw Driver", department="Logistics")
    chart = (await ac.get("/api/v1/hrm/org-chart", headers=h)).json()["data"]
    top = next(n for n in chart["roots"] if n["name"] == "Ama Boss")
    assert top["team_size"] == 2 and sorted(r["name"] for r in top["reports"]) == ["Esi Rep", "Kojo Rep"]
    assert chart["loops"] == []

    vac = await ac.post("/api/v1/hrm/vacancies", headers=h, json={"title": "Sales rep", "department": "Sales", "openings": 1})
    assert vac.status_code == 200, vac.text
    saved = await ac.put("/api/v1/hrm/headcount", headers=h, json={"department": "Sales", "planned": 5})
    assert saved.status_code == 200, saved.text
    rows = {r["department"]: r for r in saved.json()["data"]}
    assert rows["Sales"] == {"department": "Sales", "planned": 5, "filled": 3, "hiring": 1, "gap": 1}
    assert rows["Logistics"]["planned"] is None and rows["Logistics"]["filled"] == 1

    staff = await _login_staff(ac, h, "esi@alpha.example.com", "Esi Rep")
    assert (await ac.get("/api/v1/hrm/org-chart", headers=staff)).status_code == 403
