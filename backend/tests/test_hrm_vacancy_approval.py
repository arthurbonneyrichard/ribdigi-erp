"""A vacancy proposed by anyone but an HR manager waits for approval by someone else."""

from __future__ import annotations

import pytest

from tests.test_hrm_desk import _admin
from tests.test_hrm_people import _user

pytestmark = pytest.mark.asyncio
B = "/api/v1/hrm"


async def test_vacancy_approval_chain(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    assert (await ac.patch(f"{B}/settings", headers=h, json={"vacancy_approval": True})).status_code == 200
    mgr = await _user(ac, h, "dept1@alpha.example.com", "hrm_officer")
    rec = await _user(ac, h, "rec2@alpha.example.com", "hrm_recruiter")
    hrm2 = await _user(ac, h, "hrm2@alpha.example.com", "hrm_manager")

    direct = await ac.post(f"{B}/vacancies", headers=h, json={"title": "Driver", "department": "Logistics", "openings": 1})
    assert direct.json()["data"]["status"] == "open"  # an admin opens jobs directly

    prop = (await ac.post(f"{B}/vacancies", headers=mgr, json={"title": "Cashier", "department": "Sales", "openings": 2})).json()["data"]
    assert prop["status"] == "pending"
    vid = prop["id"]
    # no candidates until approved; proposer and a recruiter cannot approve
    assert (await ac.post(f"{B}/vacancies/{vid}/candidates", headers=h, json={"full_name": "Early Bird"})).status_code == 409
    assert (await ac.post(f"{B}/vacancies/{vid}/decision", headers=mgr, json={"approve": True})).status_code == 403
    assert (await ac.post(f"{B}/vacancies/{vid}/decision", headers=rec, json={"approve": True})).status_code == 403
    # turning down needs a reason
    assert (await ac.post(f"{B}/vacancies/{vid}/decision", headers=h, json={"approve": False})).status_code == 422
    ok = await ac.post(f"{B}/vacancies/{vid}/decision", headers=hrm2, json={"approve": True})
    assert ok.status_code == 200 and ok.json()["data"]["status"] == "open"
    assert (await ac.post(f"{B}/vacancies/{vid}/decision", headers=h, json={"approve": True})).status_code == 409
    assert (await ac.post(f"{B}/vacancies/{vid}/candidates", headers=h, json={"full_name": "Real Candidate"})).status_code == 200

    # a proposal that is turned down stays closed to candidates
    p2 = (await ac.post(f"{B}/vacancies", headers=mgr, json={"title": "Cleaner", "department": "Ops", "openings": 1})).json()["data"]
    no = await ac.post(f"{B}/vacancies/{p2['id']}/decision", headers=h, json={"approve": False, "note": "No budget this year"})
    assert no.json()["data"]["status"] == "rejected" and no.json()["data"]["decision_note"] == "No budget this year"
    assert (await ac.post(f"{B}/vacancies/{p2['id']}/candidates", headers=h, json={"full_name": "Late One"})).status_code == 409
