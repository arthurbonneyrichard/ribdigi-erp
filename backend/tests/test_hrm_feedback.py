"""KPI targets with progress, and 360 feedback shown without names once two colleagues answer."""

from __future__ import annotations

import pytest

from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_leave_steps import _login_staff

pytestmark = pytest.mark.asyncio


async def test_kpi_progress_and_anonymous_360(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    ama = await _person(ac, h, email="ama@alpha.example.com", full_name="Ama Mensah")
    kofi = await _person(ac, h, email="kofi@alpha.example.com", full_name="Kofi Owusu")
    esi = await _person(ac, h, email="esi@alpha.example.com", full_name="Esi Boateng")
    ama_h = await _login_staff(ac, h, "ama@alpha.example.com", "Ama Mensah")
    kofi_h = await _login_staff(ac, h, "kofi@alpha.example.com", "Kofi Owusu")
    esi_h = await _login_staff(ac, h, "esi@alpha.example.com", "Esi Boateng")

    review = await ac.post(
        "/api/v1/hrm/reviews", headers=h,
        json={"employee_id": ama["id"], "cycle": "2026 H2", "goals": [
            {"title": "Monthly sales", "weight": 70, "target": 50000, "unit": "GHS"},
            {"title": "Team work", "weight": 30},
        ]},
    )
    assert review.status_code == 200, review.text
    rid = review.json()["data"]["id"]
    mine = await ac.post(f"/api/v1/hrm/me/reviews/{rid}/progress", headers=ama_h, json={"goal": 0, "actual": 20000})
    assert mine.status_code == 200, mine.text
    assert mine.json()["data"]["goals"][0]["progress"] == 40
    assert (await ac.post(f"/api/v1/hrm/me/reviews/{rid}/progress", headers=ama_h, json={"goal": 1, "actual": 3})).status_code == 422
    assert (await ac.post(f"/api/v1/hrm/me/reviews/{rid}/progress", headers=kofi_h, json={"goal": 0, "actual": 1})).status_code == 404

    assert (await ac.post(f"/api/v1/hrm/reviews/{rid}/feedback", headers=h, json={"employee_ids": [ama["id"]]})).status_code == 422
    asked = await ac.post(f"/api/v1/hrm/reviews/{rid}/feedback", headers=h, json={"employee_ids": [kofi["id"], esi["id"]]})
    assert asked.json()["data"]["asked"] == 2
    kofi_req = (await ac.get("/api/v1/hrm/me/feedback", headers=kofi_h)).json()["data"][0]
    assert kofi_req["about"] == "Ama Mensah" and kofi_req["open"]
    assert (await ac.post(f"/api/v1/hrm/me/feedback/{kofi_req['id']}", headers=esi_h, json={"rating": 5, "strengths": "x y"})).status_code == 404
    assert (await ac.post(f"/api/v1/hrm/me/feedback/{kofi_req['id']}", headers=kofi_h, json={"rating": 4, "strengths": "Always on time"})).status_code == 200
    assert (await ac.post(f"/api/v1/hrm/me/feedback/{kofi_req['id']}", headers=kofi_h, json={"rating": 1, "strengths": "Again"})).status_code == 409

    hr_view = next(r for r in (await ac.get("/api/v1/hrm/reviews", headers=h)).json()["data"] if r["id"] == rid)
    # One answer would give its writer away: nothing shown yet, and HR sees who still has to answer.
    assert hr_view["feedback"]["given"] == 1 and hr_view["feedback"]["comments"] == [] and hr_view["feedback"]["average"] is None
    assert hr_view["feedback"]["waiting_on"] == ["Esi Boateng"]

    esi_req = (await ac.get("/api/v1/hrm/me/feedback", headers=esi_h)).json()["data"][0]
    await ac.post(f"/api/v1/hrm/me/feedback/{esi_req['id']}", headers=esi_h, json={"rating": 3, "improve": "Share the busy days"})
    staff_view = (await ac.get("/api/v1/hrm/me/more", headers=ama_h)).json()["data"]["reviews"][0]["feedback"]
    assert staff_view["average"] == 3.5 and len(staff_view["comments"]) == 2
    assert "waiting_on" in staff_view and staff_view["waiting_on"] == []
    assert all("Kofi" not in str(c) and "Esi" not in str(c) for c in staff_view["comments"])
