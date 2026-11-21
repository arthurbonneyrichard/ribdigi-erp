"""Interview panels with scores, and the training budget against recorded cost."""

from __future__ import annotations

from datetime import date

import pytest

from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_leave_steps import _login_staff
from tests.test_hrm_people import _user

pytestmark = pytest.mark.asyncio


async def test_panel_scores_average_into_the_candidate(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    kofi = await _person(ac, h, email="kofi@alpha.example.com", full_name="Kofi Owusu")
    esi = await _person(ac, h, email="esi@alpha.example.com", full_name="Esi Boateng")
    outsider = await _person(ac, h, email="yaw@alpha.example.com", full_name="Yaw Darko")
    kofi_h = await _login_staff(ac, h, "kofi@alpha.example.com", "Kofi Owusu")
    esi_h = await _login_staff(ac, h, "esi@alpha.example.com", "Esi Boateng")
    yaw_h = await _login_staff(ac, h, "yaw@alpha.example.com", "Yaw Darko")

    vac = (await ac.post("/api/v1/hrm/vacancies", headers=h, json={"title": "Cashier", "department": "Tills"})).json()["data"]
    cand = (await ac.post(f"/api/v1/hrm/vacancies/{vac['id']}/candidates", headers=h, json={"full_name": "Abena Owusu"})).json()["data"]

    bad = await ac.post(f"/api/v1/hrm/candidates/{cand['id']}/interviews", headers=h, json={"scheduled_at": "2027-01-10T09:00:00", "panel": []})
    assert bad.status_code == 422
    # staff without the recruitment job cannot schedule
    assert (await ac.post(f"/api/v1/hrm/candidates/{cand['id']}/interviews", headers=yaw_h, json={"scheduled_at": "2027-01-10T09:00:00", "panel": [kofi["id"]]})).status_code == 403

    iv = (
        await ac.post(
            f"/api/v1/hrm/candidates/{cand['id']}/interviews", headers=h,
            json={"scheduled_at": "2027-01-10T09:00:00", "location": "Head office", "panel": [kofi["id"], esi["id"], kofi["id"]]},
        )
    ).json()["data"]
    assert len(iv["panel"]) == 2  # duplicates dropped

    assert (await ac.post(f"/api/v1/hrm/interviews/{iv['id']}/done", headers=h)).status_code == 409  # nobody scored
    assert (await ac.post(f"/api/v1/hrm/me/interviews/{iv['id']}/score", headers=yaw_h, json={"score": 90})).status_code == 403
    assert (await ac.get("/api/v1/hrm/me/interviews", headers=yaw_h)).json()["data"] == []

    mine = (await ac.get("/api/v1/hrm/me/interviews", headers=kofi_h)).json()["data"]
    assert mine[0]["candidate_name"] == "Abena Owusu" and "scores" not in mine[0]
    assert (await ac.post(f"/api/v1/hrm/me/interviews/{iv['id']}/score", headers=kofi_h, json={"score": 0})).status_code == 422
    assert (await ac.post(f"/api/v1/hrm/me/interviews/{iv['id']}/score", headers=kofi_h, json={"score": 80, "comment": "Clear answers"})).status_code == 200
    assert (await ac.post(f"/api/v1/hrm/me/interviews/{iv['id']}/score", headers=kofi_h, json={"score": 10})).status_code == 409
    assert (await ac.post(f"/api/v1/hrm/me/interviews/{iv['id']}/score", headers=esi_h, json={"score": 61})).status_code == 200

    shown = (await ac.get(f"/api/v1/hrm/candidates/{cand['id']}/interviews", headers=h)).json()["data"][0]
    assert shown["average"] == 70.5 and shown["scored_by"] == 2

    done = await ac.post(f"/api/v1/hrm/interviews/{iv['id']}/done", headers=h)
    assert done.status_code == 200 and done.json()["data"]["status"] == "done"
    rows = (await ac.get(f"/api/v1/hrm/vacancies/{vac['id']}/candidates", headers=h)).json()["data"]
    assert rows[0]["score"] in (70, 71)
    assert (await ac.post(f"/api/v1/hrm/me/interviews/{iv['id']}/score", headers=kofi_h, json={"score": 50})).status_code in (403, 409)
    del outsider


async def test_interviews_stay_inside_the_company(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    from app import models as m

    theirs = m.HrmEmployee(tenant_id=seed["t2"].id, employee_number="EMP-X", full_name="Theirs", hired_on=date.today(), status="active")
    db_session.add(theirs)
    await db_session.commit()
    vac = (await ac.post("/api/v1/hrm/vacancies", headers=h, json={"title": "Guard", "department": "Site"})).json()["data"]
    cand = (await ac.post(f"/api/v1/hrm/vacancies/{vac['id']}/candidates", headers=h, json={"full_name": "Kojo Mensah"})).json()["data"]
    r = await ac.post(f"/api/v1/hrm/candidates/{cand['id']}/interviews", headers=h, json={"scheduled_at": "2027-01-10T09:00:00", "panel": [theirs.id]})
    assert r.status_code == 404  # another company's staff cannot sit on the panel


async def test_training_budget_against_cost(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    officer = await _user(ac, h, "officer@alpha.example.com", "hrm_officer")
    ama = await _person(ac, h, email="ama@alpha.example.com", full_name="Ama Mensah")
    year = date.today().year
    course = (await ac.post("/api/v1/hrm/trainings", headers=h, json={"title": "Fire safety", "mandatory": True})).json()["data"]

    assert (await ac.get("/api/v1/hrm/trainings/budget", headers=officer)).status_code == 403
    assert (await ac.put("/api/v1/hrm/trainings/budget", headers=officer, json={"year": year, "amount": 1000})).status_code == 403
    assert (await ac.put("/api/v1/hrm/trainings/budget", headers=h, json={"year": year, "amount": -1})).status_code == 422
    assert (await ac.put("/api/v1/hrm/trainings/budget", headers=h, json={"year": year, "amount": 1000})).status_code == 200

    done_on = date.today().isoformat()
    for cost in (400, 700):
        r = await ac.post(
            "/api/v1/hrm/training-records", headers=h,
            json={"training_id": course["id"], "employee_id": ama["id"], "completed_on": done_on, "cost": cost},
        )
        assert r.status_code == 200, r.text
    b = (await ac.get(f"/api/v1/hrm/trainings/budget?year={year}", headers=h)).json()["data"]
    assert b["budget"] == 1000 and b["spent"] == 1100 and b["left"] == -100 and b["over_budget"] is True

    # costs are for HR managers: officers see the records without them
    listed = (await ac.get("/api/v1/hrm/trainings", headers=officer)).json()["data"]
    assert listed["budget"] is None and all("cost" not in r for r in listed["records"])
    assert all("cost" in r for r in (await ac.get("/api/v1/hrm/trainings", headers=h)).json()["data"]["records"])
