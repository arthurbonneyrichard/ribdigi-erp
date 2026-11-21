"""FMCG staff location: switched on per person, notice accepted, clocked in only, scoped to the manager,
audited, and purged after 30 days."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app import fmcg_tracking
from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

T = "/api/v1/fmcg/tracking"


async def _user(ac, db_session, seed, email, role):
    db_session.add(
        m.User(
            tenant_id=seed["t1"].id, email=email, full_name=email.split("@")[0].title(),
            password_hash=hash_password("SecurePass123!"), role=role, email_verified=True,
            permissions=permissions_for_role(role), totp_enabled=False,
        )
    )
    await db_session.commit()
    user = (await db_session.execute(select(m.User).where(m.User.email == email))).scalar_one()
    return user.id, await auth_headers(ac, email=email, tenant_slug="alpha")


async def _employee(db_session, seed, email, *, manager_id=None, clocked_in=False):
    emp = m.HrmEmployee(
        tenant_id=seed["t1"].id, employee_number=f"E{uuid4().hex[:6]}", full_name=email.split("@")[0],
        email=email, hired_on=date(2024, 1, 1), status="active", manager_id=manager_id,
    )
    db_session.add(emp)
    await db_session.flush()
    if clocked_in:
        db_session.add(m.HrmClockEvent(tenant_id=seed["t1"].id, employee_id=emp.id, kind="in", at=datetime.utcnow(), source="hr"))
    await db_session.commit()
    return emp.id


def _pt(minutes_ago: float, lat: float, lon: float, acc: float = 12):
    at = (datetime.utcnow() - timedelta(minutes=minutes_ago)).replace(microsecond=0)
    return {"latitude": lat, "longitude": lon, "accuracy_m": acc, "captured_at": at.isoformat() + "Z"}


@pytest.mark.asyncio
async def test_only_fmcg_companies(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "retail")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    res = await ac.get(f"{T}/me", headers=admin)
    assert res.status_code == 403 and res.json()["detail"]["code"] in {"FMCG_ONLY", "INDUSTRY_MODULE_DISABLED"}
    assert (await ac.get(f"{T}/people", headers=admin)).status_code == 403


@pytest.mark.asyncio
async def test_pings_need_switch_notice_and_clock_in_then_trail_and_audit(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    rep_id, rep = await _user(ac, db_session, seed, "kofi.rep@alpha.example.com", "fmcg_rep")
    emp_id = await _employee(db_session, seed, "kofi.rep@alpha.example.com")
    send = lambda pts: ac.post(f"{T}/pings", headers=rep, json={"points": pts})  # noqa: E731

    off = await send([_pt(1, 5.6, -0.19)])
    assert off.status_code == 403 and off.json()["detail"]["code"] == "TRACKING_OFF"
    assert (await ac.put(f"{T}/people/{rep_id}", headers=rep, json={"enabled": True})).status_code == 403  # staff cannot switch themselves on

    assert (await ac.put(f"{T}/people/{rep_id}", headers=admin, json={"enabled": True})).status_code == 200
    me = (await ac.get(f"{T}/me", headers=rep)).json()["data"]
    assert me["enabled"] and not me["notice_accepted"] and not me["sharing"] and me["has_hr_record"]

    assert (await send([_pt(1, 5.6, -0.19)])).json()["detail"]["code"] == "NOTICE_NEEDED"
    assert (await ac.post(f"{T}/me/notice", headers=rep)).status_code == 200
    assert (await send([_pt(1, 5.6, -0.19)])).json()["detail"]["code"] == "NOT_CLOCKED_IN"

    db_session.add(m.HrmClockEvent(tenant_id=seed["t1"].id, employee_id=emp_id, kind="in", at=datetime.utcnow() - timedelta(hours=1), source="hr"))
    await db_session.commit()
    assert (await ac.get(f"{T}/me", headers=rep)).json()["data"]["sharing"] is True

    # A stop of 12 minutes in one place, then 1.1 km north. Rough, future and duplicate points do not count.
    stay = [_pt(17, 5.6000, -0.1900), _pt(13, 5.6001, -0.1900), _pt(9, 5.6000, -0.1901), _pt(5, 5.6001, -0.1901), _pt(1, 5.6100, -0.1900)]
    junk = [_pt(3, 5.7, -0.2, acc=900), _pt(-30, 5.7, -0.2)]
    res = await send(stay + junk)
    assert res.status_code == 200, res.text
    assert res.json()["data"] == {"saved": 5, "dropped": 2, "duplicates": 0}
    again = await send(stay[:2])
    assert again.json()["data"]["saved"] == 0 and again.json()["data"]["duplicates"] == 2
    too_many = await send([_pt(i / 10, 5.6, -0.19) for i in range(101)])
    assert too_many.status_code == 422

    live = (await ac.get(f"{T}/people", headers=admin)).json()["data"]
    row = next(p for p in live["people"] if p["user_id"] == rep_id)
    assert live["can_switch"] is True
    assert row["on_duty"] and not row["stale"] and row["latitude"] == 5.61 and row["minutes_ago"] <= 3

    day = (datetime.utcnow() - timedelta(minutes=17)).date().isoformat()
    trail = (await ac.get(f"{T}/people/{rep_id}/trail", headers=admin, params={"day": day})).json()["data"]
    assert len(trail["points"]) >= 1
    if len(trail["points"]) == 5:  # (not checked in the 17 minutes after midnight UTC)
        assert 1.0 < trail["distance_km"] < 1.4
        assert len(trail["stops"]) == 1 and trail["stops"][0]["minutes"] >= 10

    audited = (
        await db_session.execute(select(m.AuditLog).where(m.AuditLog.action == "fmcg_tracking_trail_viewed", m.AuditLog.entity_id == rep_id))
    ).scalars().all()
    assert len(audited) == 1  # the manager's view is on record
    own = await ac.get(f"{T}/people/{rep_id}/trail", headers=rep, params={"day": day})
    assert own.status_code == 200
    audited = (
        await db_session.execute(select(m.AuditLog).where(m.AuditLog.action == "fmcg_tracking_trail_viewed", m.AuditLog.entity_id == rep_id))
    ).scalars().all()
    assert len(audited) == 1  # looking at your own trail is not logged

    # Switching off stops everything and asks for acceptance again next time.
    assert (await ac.put(f"{T}/people/{rep_id}", headers=admin, json={"enabled": False})).status_code == 200
    assert (await send([_pt(1, 5.6, -0.19)])).json()["detail"]["code"] == "TRACKING_OFF"


@pytest.mark.asyncio
async def test_a_manager_sees_only_the_people_who_report_to_them(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    mgr_id, mgr = await _user(ac, db_session, seed, "ama.lead@alpha.example.com", "fmcg_storekeeper")
    rep1_id, _ = await _user(ac, db_session, seed, "yaw.one@alpha.example.com", "fmcg_rep")
    rep2_id, _ = await _user(ac, db_session, seed, "esi.two@alpha.example.com", "fmcg_rep")
    lone_id, lone = await _user(ac, db_session, seed, "kojo.none@alpha.example.com", "fmcg_driver")
    mgr_emp = await _employee(db_session, seed, "ama.lead@alpha.example.com")
    await _employee(db_session, seed, "yaw.one@alpha.example.com", manager_id=mgr_emp)
    await _employee(db_session, seed, "esi.two@alpha.example.com")
    await _employee(db_session, seed, "kojo.none@alpha.example.com")

    mine = (await ac.get(f"{T}/people", headers=mgr)).json()["data"]
    assert [p["user_id"] for p in mine["people"]] == [rep1_id] and mine["can_switch"] is False
    assert (await ac.get(f"{T}/people/{rep1_id}/trail", headers=mgr)).status_code == 200
    assert (await ac.get(f"{T}/people/{rep2_id}/trail", headers=mgr)).status_code == 404  # not their team
    assert (await ac.put(f"{T}/people/{rep1_id}", headers=mgr, json={"enabled": True})).status_code in (403,)  # only HR or an admin switches on
    nobody = await ac.get(f"{T}/people", headers=lone)
    assert nobody.status_code == 403 and nobody.json()["detail"]["code"] == "TRACKING_NOT_YOURS"
    everyone = (await ac.get(f"{T}/people", headers=admin)).json()["data"]["people"]
    assert {rep1_id, rep2_id, lone_id, mgr_id} <= {p["user_id"] for p in everyone}


@pytest.mark.asyncio
async def test_points_older_than_30_days_are_deleted(client, seeded, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    uid = str(uuid4())
    now = datetime.utcnow().replace(microsecond=0)
    for days in (45, 31, 5):
        db_session.add(m.FmcgTrackPing(tenant_id=seed["t1"].id, user_id=uid, latitude=5.6, longitude=-0.19, captured_at=now - timedelta(days=days)))
    await db_session.commit()
    gone = await fmcg_tracking.purge_old(db_session, seed["t1"].id)
    await db_session.commit()
    left = (await db_session.execute(select(m.FmcgTrackPing).where(m.FmcgTrackPing.user_id == uid))).scalars().all()
    assert gone == 2 and len(left) == 1
