"""Case file: investigation notes, evidence, suspension, appeals."""

from __future__ import annotations

import pytest

from app import storage as storage_svc
from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_documents import _file
from tests.test_hrm_people import _user

pytestmark = pytest.mark.asyncio
B = "/api/v1/hrm"


async def test_case_file_and_appeal(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h, email="case2@alpha.example.com")
    staff = await _user(ac, h, "case2@alpha.example.com", "hrm_employee")
    officer = await _user(ac, h, "off3@alpha.example.com", "hrm_officer")
    boss = await _user(ac, h, "boss3@alpha.example.com", "hrm_manager")

    case = (await ac.post(f"{B}/cases", headers=h, json={"employee_id": p["id"], "kind": "disciplinary", "subject": "Cash short", "details": "Till short twice"})).json()["data"]
    cid = case["id"]

    # confidential: officers and the person themself get nothing
    assert (await ac.get(f"{B}/cases/{cid}/events", headers=officer)).status_code == 403
    assert (await ac.post(f"{B}/cases/{cid}/notes", headers=staff, json={"note": "I am fine"})).status_code == 403

    assert (await ac.post(f"{B}/cases/{cid}/notes", headers=h, json={"note": "Interviewed the supervisor"})).status_code == 200
    ev = await ac.post(f"{B}/cases/{cid}/evidence", headers=h, files=_file("till.pdf"), data={"note": "Till report"})
    assert ev.status_code == 200, ev.text
    assert (await ac.get(f"{B}/cases/evidence/{ev.json()['data']['id']}/file", headers=h)).status_code == 200
    assert (await ac.get(f"{B}/cases/evidence/{ev.json()['data']['id']}/file", headers=staff)).status_code == 403
    assert (await ac.post(f"{B}/cases/{cid}/suspension", headers=h, json={"starts_on": "2026-11-20", "ends_on": "2026-11-10", "note": "Pending hearing"})).status_code == 422
    assert (await ac.post(f"{B}/cases/{cid}/suspension", headers=h, json={"starts_on": "2026-11-20", "note": "Pending hearing"})).status_code == 200

    # no appeal until closed
    assert (await ac.post(f"{B}/me/cases/{cid}/appeal", headers=staff, json={"reason": "Unfair finding"})).status_code == 409
    closed = await ac.patch(f"{B}/cases/{cid}", headers=h, json={"close": True, "outcome": "written_warning", "outcome_note": "Warning issued"})
    assert closed.status_code == 200, closed.text
    assert (await ac.post(f"{B}/cases/{cid}/notes", headers=h, json={"note": "late note"})).status_code == 409

    st = (await ac.get(f"{B}/me/cases/{cid}/appeal", headers=staff)).json()["data"]
    assert st["can_appeal"] is True
    ok = await ac.post(f"{B}/me/cases/{cid}/appeal", headers=staff, json={"reason": "Unfair finding"})
    assert ok.status_code == 200 and ok.json()["data"]["appeal"]
    assert (await ac.post(f"{B}/me/cases/{cid}/appeal", headers=staff, json={"reason": "Again please"})).status_code == 409

    # the closer cannot decide their own case's appeal; a second HR manager can
    assert (await ac.post(f"{B}/cases/{cid}/appeal/decision", headers=h, json={"outcome": "rejected", "note": "Stands"})).status_code == 403
    done = await ac.post(f"{B}/cases/{cid}/appeal/decision", headers=boss, json={"outcome": "upheld", "note": "Warning withdrawn"})
    assert done.status_code == 200, done.text
    assert done.json()["data"]["decision"]["outcome"] == "upheld"
    mine = (await ac.get(f"{B}/me/cases/{cid}/appeal", headers=staff)).json()["data"]
    assert mine["decision"]["outcome"] == "upheld" and "events" not in mine
    # staff never see investigation notes
    tl = (await ac.get(f"{B}/cases/{cid}/events", headers=boss)).json()["data"]["events"]
    assert {e["kind"] for e in tl} >= {"investigation", "evidence", "suspension", "appeal", "appeal_decision"}


async def test_appeal_only_for_own_case(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a = await _person(ac, h, email="a4@alpha.example.com")
    await _person(ac, h, email="b4@alpha.example.com")
    other = await _user(ac, h, "b4@alpha.example.com", "hrm_employee")
    case = (await ac.post(f"{B}/cases", headers=h, json={"employee_id": a["id"], "kind": "grievance", "subject": "Rota unfair", "details": "Always nights"})).json()["data"]
    await ac.patch(f"{B}/cases/{case['id']}", headers=h, json={"close": True, "outcome": "not_upheld", "outcome_note": "Rota fair"})
    assert (await ac.post(f"{B}/me/cases/{case['id']}/appeal", headers=other, json={"reason": "Not mine"})).status_code == 404
