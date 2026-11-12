"""HRM people work: hiring through the stages, reviews, training, contracts and probation,
confidential cases, assets, expense claims and notices, with each HR role's limits."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.conftest import auth_headers
from tests.test_hrm_desk import _admin, _even, _person

pytestmark = pytest.mark.asyncio


async def _user(ac, h, email, role):
    r = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": email, "full_name": email.split("@")[0].title(), "password": "SecurePass123!", "role": role},
    )
    assert r.status_code == 200, r.text
    return await auth_headers(ac, email=email, tenant_slug="alpha")


async def test_hiring_moves_stage_by_stage_and_makes_a_staff_record(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    officer = await _user(ac, h, "officer@alpha.example.com", "hrm_officer")
    vac = (await ac.post("/api/v1/hrm/vacancies", headers=officer, json={"title": "Store keeper", "department": "Stores"})).json()["data"]
    cand = (
        await ac.post(
            f"/api/v1/hrm/vacancies/{vac['id']}/candidates", headers=officer,
            json={"full_name": "Abena Owusu", "email": "abena@example.com"},
        )
    ).json()["data"]
    skip = await ac.post(f"/api/v1/hrm/candidates/{cand['id']}/move", headers=officer, json={"stage": "offer", "offered_basic": 1800})
    assert skip.status_code == 403  # an offer names pay: officers cannot
    jump = await ac.post(f"/api/v1/hrm/candidates/{cand['id']}/move", headers=h, json={"stage": "interview"})
    assert jump.status_code == 409  # one stage at a time
    for stage in ("screening", "interview"):
        r = await ac.post(f"/api/v1/hrm/candidates/{cand['id']}/move", headers=officer, json={"stage": stage, "score": 70})
        assert r.status_code == 200, r.text
    no_pay = await ac.post(f"/api/v1/hrm/candidates/{cand['id']}/move", headers=h, json={"stage": "offer"})
    assert no_pay.status_code == 422
    offer = await ac.post(f"/api/v1/hrm/candidates/{cand['id']}/move", headers=h, json={"stage": "offer", "offered_basic": 1800})
    assert offer.status_code == 200, offer.text
    listed = (await ac.get(f"/api/v1/hrm/vacancies/{vac['id']}/candidates", headers=officer)).json()["data"]
    assert "offered_basic" not in listed[0]
    hired = await ac.post(
        f"/api/v1/hrm/candidates/{cand['id']}/hire", headers=h, json={"starts_on": "2027-01-04", "probation_months": 3}
    )
    assert hired.status_code == 200, hired.text
    staff = hired.json()["data"]
    assert staff["full_name"] == "Abena Owusu" and staff["basic_salary"] == 1800 and staff["job_title"] == "Store keeper"
    contracts = (await ac.get("/api/v1/hrm/contracts", headers=h)).json()["data"]["contracts"]
    assert contracts[0]["probation_ends_on"] == "2027-04-04"
    vacs = (await ac.get("/api/v1/hrm/vacancies", headers=h)).json()["data"]
    assert vacs[0]["status"] == "filled"


async def test_review_self_then_reviewer_with_weighted_score(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, email="rev@alpha.example.com")
    staff = await _user(ac, h, "rev@alpha.example.com", "hrm_employee")
    bad = await ac.post(
        "/api/v1/hrm/reviews", headers=h,
        json={"employee_id": person["id"], "cycle": "2026", "goals": [{"title": "Sales", "weight": 50}]},
    )
    assert bad.status_code == 422  # weights must make 100
    rev = (
        await ac.post(
            "/api/v1/hrm/reviews", headers=h,
            json={"employee_id": person["id"], "cycle": "2026", "goals": [{"title": "Sales", "weight": 60}, {"title": "Punctuality", "weight": 40}]},
        )
    ).json()["data"]
    assert (await ac.get("/api/v1/hrm/reviews", headers=staff)).status_code == 403
    mine = await ac.post(f"/api/v1/hrm/me/reviews/{rev['id']}/self", headers=staff, json={"scores": [4, 5], "comment": "Good year"})
    assert mine.status_code == 200, mine.text
    own = await ac.post(f"/api/v1/hrm/reviews/{rev['id']}/complete", headers=staff, json={"scores": [5, 5]})
    assert own.status_code == 403
    done = await ac.post(f"/api/v1/hrm/reviews/{rev['id']}/complete", headers=h, json={"scores": [3, 5], "comment": "Solid"})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["overall"] == 3.8  # (3*60 + 5*40) / 100


async def test_training_expiry_and_mandatory_gaps(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a = await _person(ac, h)
    b = await _person(ac, h)
    course = (await ac.post("/api/v1/hrm/trainings", headers=h, json={"title": "Fire safety", "mandatory": True, "valid_months": 12})).json()["data"]
    old = (date.today() - timedelta(days=400)).isoformat()
    rec = await ac.post("/api/v1/hrm/training-records", headers=h, json={"training_id": course["id"], "employee_id": a["id"], "completed_on": old})
    assert rec.status_code == 200, rec.text
    assert rec.json()["data"]["state"] == "expired"
    future = await ac.post(
        "/api/v1/hrm/training-records", headers=h,
        json={"training_id": course["id"], "employee_id": b["id"], "completed_on": (date.today() + timedelta(days=3)).isoformat()},
    )
    assert future.status_code == 422
    gaps = (await ac.get("/api/v1/hrm/trainings", headers=h)).json()["data"]["gaps"]
    whys = {(g["employee_id"], g["why"].split()[0]) for g in gaps}
    assert (a["id"], "lapsed") in whys and (b["id"], "not") in whys


async def test_contract_alerts_and_probation_confirmation(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h)
    soon = (date.today() + timedelta(days=10)).isoformat()
    no_end = await ac.post("/api/v1/hrm/contracts", headers=h, json={"employee_id": p["id"], "kind": "fixed_term", "starts_on": "2026-01-01"})
    assert no_end.status_code == 422
    c = (
        await ac.post(
            "/api/v1/hrm/contracts", headers=h,
            json={"employee_id": p["id"], "kind": "fixed_term", "starts_on": "2026-01-01", "ends_on": soon, "probation_ends_on": soon},
        )
    ).json()["data"]
    alerts = (await ac.get("/api/v1/hrm/contracts", headers=h)).json()["data"]["alerts"]
    assert [x["id"] for x in alerts["contracts_ending"]] == [c["id"]]
    assert [x["id"] for x in alerts["probation_due"]] == [c["id"]]
    ok = await ac.post(f"/api/v1/hrm/contracts/{c['id']}/confirm", headers=h)
    assert ok.status_code == 200 and ok.json()["data"]["confirmed_on"]
    alerts = (await ac.get("/api/v1/hrm/contracts", headers=h)).json()["data"]["alerts"]
    assert alerts["probation_due"] == []


async def test_cases_are_confidential_and_close_with_an_outcome(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, email="case@alpha.example.com")
    officer = await _user(ac, h, "officer2@alpha.example.com", "hrm_officer")
    staff = await _user(ac, h, "case@alpha.example.com", "hrm_employee")
    assert (await ac.get("/api/v1/hrm/cases", headers=officer)).status_code == 403
    griev = await ac.post("/api/v1/hrm/me/grievances", headers=staff, json={"subject": "Shift rota", "details": "Always given the late shift"})
    assert griev.status_code == 200, griev.text
    assert "details" not in griev.json()["data"]
    case = (
        await ac.post(
            "/api/v1/hrm/cases", headers=h,
            json={"employee_id": person["id"], "kind": "disciplinary", "subject": "Late three times", "details": "Logged on 2, 9 and 16 Nov"},
        )
    ).json()["data"]
    bad = await ac.patch(f"/api/v1/hrm/cases/{case['id']}", headers=h, json={"close": True, "outcome": "upheld", "outcome_note": "x x"})
    assert bad.status_code == 422
    closed = await ac.patch(
        f"/api/v1/hrm/cases/{case['id']}", headers=h,
        json={"close": True, "outcome": "written_warning", "outcome_note": "Warning given at hearing"},
    )
    assert closed.status_code == 200 and closed.json()["data"]["status"] == "closed"
    mine = (await ac.get("/api/v1/hrm/me/more", headers=staff)).json()["data"]["cases"]
    assert {c["kind"] for c in mine} == {"grievance", "disciplinary"}
    assert all("details" not in c and "outcome_note" not in c for c in mine)


async def test_assets_and_claims_paid_back_by_someone_else(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, email="claim@alpha.example.com")
    staff = await _user(ac, h, "claim@alpha.example.com", "hrm_employee")
    item = (
        await ac.post("/api/v1/hrm/assets", headers=h, json={"employee_id": person["id"], "item": "Dell laptop", "kind": "laptop", "issued_on": "2026-02-01"})
    ).json()["data"]
    assert len((await ac.get("/api/v1/hrm/me/more", headers=staff)).json()["data"]["assets"]) == 1
    back = await ac.post(f"/api/v1/hrm/assets/{item['id']}/return", headers=h, json={"returned_on": "2026-10-01", "condition": "Good"})
    assert back.status_code == 200
    again = await ac.post(f"/api/v1/hrm/assets/{item['id']}/return", headers=h, json={"returned_on": "2026-10-02", "condition": "Good"})
    assert again.status_code == 409

    claim = (
        await ac.post("/api/v1/hrm/me/claims", headers=staff, json={"spent_on": "2026-10-03", "description": "Taxi to supplier", "amount": 85})
    ).json()["data"]
    assert (await ac.post(f"/api/v1/hrm/claims/{claim['id']}/decide", headers=staff, json={"approve": True, "method": "cash"})).status_code == 403
    paid = await ac.post(f"/api/v1/hrm/claims/{claim['id']}/decide", headers=h, json={"approve": True, "method": "cash"})
    assert paid.status_code == 200, paid.text
    assert paid.json()["data"]["status"] == "paid"
    await _even(ac, h)


async def test_notices_reach_staff_until_taken_down(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h, email="read@alpha.example.com")
    staff = await _user(ac, h, "read@alpha.example.com", "hrm_employee")
    n = (await ac.post("/api/v1/hrm/notices", headers=h, json={"kind": "policy", "title": "Leave policy", "body": "Ask two weeks ahead."})).json()["data"]
    assert [x["title"] for x in (await ac.get("/api/v1/hrm/me/more", headers=staff)).json()["data"]["notices"]] == ["Leave policy"]
    assert (await ac.post("/api/v1/hrm/notices", headers=staff, json={"kind": "policy", "title": "Mine", "body": "No"})).status_code == 403
    await ac.post(f"/api/v1/hrm/notices/{n['id']}/retire", headers=h)
    assert (await ac.get("/api/v1/hrm/me/more", headers=staff)).json()["data"]["notices"] == []


async def test_dashboard_lists_people_work_coming_due(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h)
    soon = (date.today() + timedelta(days=5)).isoformat()
    await ac.post("/api/v1/hrm/contracts", headers=h, json={"employee_id": p["id"], "kind": "fixed_term", "starts_on": "2026-01-01", "ends_on": soon})
    await ac.post("/api/v1/hrm/trainings", headers=h, json={"title": "First aid", "mandatory": True})
    summary = (await ac.get("/api/v1/hrm/summary", headers=h)).json()["data"]
    words = " ".join(item.get("text") or item.get("label") or str(item) for item in summary["attention"])
    assert "contract" in words and "mandatory course" in words
