"""Onboarding/offboarding, exit interview, benefits, career history, OKRs, custom fields, succession."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers
from tests.test_hrm_desk import _admin, _person
from tests.test_hrm_leave_steps import _login_staff

pytestmark = pytest.mark.asyncio
B = "/api/v1/hrm"


async def test_checklists_and_asset_clearance(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h)
    r = await ac.post(f"{B}/employees/{p['id']}/checklist", headers=h, json={"kind": "onboarding"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["total"] >= 5 and not r.json()["data"]["complete"]
    assert (await ac.post(f"{B}/employees/{p['id']}/checklist", headers=h, json={"kind": "onboarding"})).status_code == 409

    asset = await ac.post(f"{B}/assets", headers=h, json={"employee_id": p["id"], "item": "Laptop", "kind": "laptop", "issued_on": "2025-01-10", "serial": "SN1"})
    assert asset.status_code == 200, asset.text
    out = (await ac.post(f"{B}/employees/{p['id']}/checklist", headers=h, json={"kind": "offboarding"})).json()["data"]
    recover = next(t for t in out["tasks"] if t["asset_id"])
    assert "Laptop" in recover["title"]
    # cannot tick the recovery until the laptop is booked back in
    assert (await ac.post(f"{B}/checklist/tasks/{recover['id']}/done", headers=h)).status_code == 409
    back = await ac.post(f"{B}/assets/{asset.json()['data']['id']}/return", headers=h, json={"returned_on": "2026-11-19", "condition": "Good"})
    assert back.status_code == 200, back.text
    for t in out["tasks"]:
        res = await ac.post(f"{B}/checklist/tasks/{t['id']}/done", headers=h)
        assert res.status_code == 200, res.text
    final = (await ac.get(f"{B}/employees/{p['id']}/checklist/offboarding", headers=h)).json()["data"]
    assert final["complete"] is True
    assert (await ac.get(f"{B}/checklists", headers=h)).json()["data"][0]["kind"] == "onboarding"

    iv = await ac.put(f"{B}/employees/{p['id']}/exit-interview", headers=h, json={"held_on": "2026-11-19", "reason_category": "relocation", "would_return": True, "feedback": "Moving to Kumasi"})
    assert iv.status_code == 200, iv.text
    assert (await ac.put(f"{B}/employees/{p['id']}/exit-interview", headers=h, json={"held_on": "2026-11-19", "reason_category": "nonsense"})).status_code == 422


async def test_benefits_career_custom_fields_succession(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h, job_title="Cashier", department="Sales")
    q = await _person(ac, h)

    b = await ac.post(f"{B}/employees/{p['id']}/benefits", headers=h, json={"kind": "insurance", "name": "Group health", "provider": "Acme", "starts_on": "2026-01-01"})
    assert b.status_code == 200 and b.json()["data"]["active"] is True
    assert (await ac.post(f"{B}/employees/{p['id']}/benefits", headers=h, json={"kind": "insurance", "name": "Bad", "starts_on": "2026-02-01", "ends_on": "2026-01-01"})).status_code == 422
    ended = await ac.post(f"{B}/benefits/{b.json()['data']['id']}/end", headers=h, json={"ends_on": "2026-06-30"})
    assert ended.json()["data"]["active"] is False

    c = await ac.post(f"{B}/employees/{p['id']}/career", headers=h, json={"kind": "promotion", "effective_on": "2026-11-01", "to_job_title": "Supervisor"})
    assert c.status_code == 200, c.text
    assert c.json()["data"]["from_job_title"] == "Cashier"
    hist = (await ac.get(f"{B}/employees/{p['id']}/career", headers=h)).json()["data"]
    assert hist[0]["to_job_title"] == "Supervisor"
    assert (await ac.post(f"{B}/employees/{p['id']}/career", headers=h, json={"kind": "transfer", "effective_on": "2099-01-01", "to_department": "X1"})).status_code == 422
    assert (await ac.post(f"{B}/employees/{p['id']}/career", headers=h, json={"kind": "promotion", "effective_on": "2026-11-02"})).status_code == 422

    f = await ac.post(f"{B}/custom-fields", headers=h, json={"label": "Shoe size", "kind": "number"})
    assert f.status_code == 200, f.text
    fid = f.json()["data"]["id"]
    assert (await ac.post(f"{B}/custom-fields", headers=h, json={"label": "Shoe size"})).status_code == 409
    assert (await ac.put(f"{B}/employees/{p['id']}/custom/{fid}", headers=h, json={"value": "big"})).status_code == 422
    ok = await ac.put(f"{B}/employees/{p['id']}/custom/{fid}", headers=h, json={"value": "42"})
    assert ok.json()["data"][0]["value"] == "42"

    s = await ac.post(f"{B}/succession", headers=h, json={"position": "Store manager", "incumbent_id": p["id"], "successor_id": q["id"], "readiness": "one_two_years"})
    assert s.status_code == 200, s.text
    assert (await ac.post(f"{B}/succession", headers=h, json={"position": "Store manager", "incumbent_id": q["id"], "successor_id": q["id"], "readiness": "ready_now"})).status_code == 422
    assert len((await ac.get(f"{B}/succession", headers=h)).json()["data"]) == 1


async def test_okrs_and_self_view(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h, email="okr@alpha.example.com", full_name="Okr Person")
    o = await ac.post(f"{B}/objectives", headers=h, json={"level": "employee", "employee_id": p["id"], "period": "2026-Q4", "title": "Grow weekly sales"})
    assert o.status_code == 200, o.text
    oid = o.json()["data"]["id"]
    assert (await ac.post(f"{B}/objectives", headers=h, json={"kind": "key_result", "parent_id": oid, "title": "Sales target", "target": 0})).status_code == 422
    kr = await ac.post(f"{B}/objectives", headers=h, json={"kind": "key_result", "parent_id": oid, "title": "Reach GHS 10000", "target": 10000, "unit": "GHS"})
    assert kr.status_code == 200, kr.text
    up = await ac.patch(f"{B}/objectives/{kr.json()['data']['id']}", headers=h, json={"current": 2500})
    assert up.json()["data"]["progress"] == 25.0
    listed = (await ac.get(f"{B}/objectives?period=2026-Q4", headers=h)).json()["data"]
    assert listed[0]["progress"] == 25.0 and len(listed[0]["key_results"]) == 1

    staff = await _login_staff(ac, h, "okr@alpha.example.com", "Okr Person")
    mine = (await ac.get(f"{B}/me/objectives", headers=staff)).json()["data"]
    assert [x["title"] for x in mine] == ["Grow weekly sales"]
    # staff cannot read the company-wide list or HR-only records
    assert (await ac.get(f"{B}/objectives", headers=staff)).status_code == 403
    assert (await ac.get(f"{B}/succession", headers=staff)).status_code == 403
    assert (await ac.post(f"{B}/custom-fields", headers=staff, json={"label": "Hack"})).status_code == 403
    assert (await ac.get(f"{B}/employees/{p['id']}/benefits", headers=staff)).status_code == 403


async def test_other_company_cannot_touch(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _person(ac, h)
    await ac.post(f"{B}/employees/{p['id']}/checklist", headers=h, json={"kind": "onboarding"})
    from tests.conftest import set_tenant_industry

    await set_tenant_industry(db_session, seed["t2"], "hrm")
    from app import models as m
    from app.security import hash_password

    db_session.add(m.User(tenant_id=seed["t2"].id, email="admin@beta.example.com", full_name="Beta Admin",
                          password_hash=hash_password("SecurePass123!"), role="company_admin", email_verified=True))
    await db_session.commit()
    beta = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    assert (await ac.get(f"{B}/employees/{p['id']}/checklist/onboarding", headers=beta)).status_code == 404
    assert (await ac.post(f"{B}/employees/{p['id']}/benefits", headers=beta, json={"kind": "other", "name": "Spy", "starts_on": "2026-01-01"})).status_code == 404
    assert (await ac.get(f"{B}/checklists", headers=beta)).json()["data"] == []
