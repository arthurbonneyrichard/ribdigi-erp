"""Gym CRM: leads, conversion, consent and campaigns."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _member, _open, _plan, _sell


@pytest.mark.asyncio
async def test_lead_follow_up_trial_conversion_and_report(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    assert (await ac.post("/api/v1/gym/leads", headers=h, json={"full_name": "Efua Boateng"})).status_code == 422
    due = (date.today() - timedelta(days=1)).isoformat()
    made = await ac.post("/api/v1/gym/leads", headers=h, json={"full_name": "Efua Boateng", "phone": "+233241234567", "source": "social", "next_follow_up": due, "marketing_consent": True})
    assert made.status_code == 200, made.text
    lead = made.json()["data"]
    assert (await ac.post("/api/v1/gym/leads", headers=h, json={"full_name": "Efua B", "phone": "+233241234567"})).status_code == 409
    assert [x["id"] for x in (await ac.get("/api/v1/gym/leads/follow-ups", headers=h)).json()["data"]] == [lead["id"]]
    t = (await ac.post(f"/api/v1/gym/leads/{lead['id']}", headers=h, json={"status": "trial", "notes": "Came for a tour"})).json()["data"]
    assert t["status"] == "trial" and t["trial_ends_on"] == (date.today() + timedelta(days=3)).isoformat()
    conv = await ac.post(f"/api/v1/gym/leads/{lead['id']}/convert", headers=h)
    assert conv.status_code == 200, conv.text
    assert (await ac.post(f"/api/v1/gym/leads/{lead['id']}/convert", headers=h)).status_code == 409
    assert (await ac.post(f"/api/v1/gym/leads/{lead['id']}", headers=h, json={"status": "lost"})).status_code == 409
    member = (await db_session.execute(select(m.GymMember).where(m.GymMember.id == conv.json()["data"]["member_id"]))).scalar_one()
    assert member.marketing_consent is True
    rep = (await ac.get("/api/v1/gym/reports/leads", headers=h)).json()["data"]
    assert rep["total"] == 1 and rep["converted"] == 1 and rep["conversion_rate"] == 100.0
    assert rep["trials"] == 1 and rep["trial_conversion_rate"] == 100.0 and rep["by_source"]["social"]["converted"] == 1


@pytest.mark.asyncio
async def test_marketing_respects_consent_and_unsubscribes_and_never_double_sends(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    plan = await _plan(ac, h)
    yes, no = await _member(ac, h), await _member(ac, h)
    for mem, phone in ((yes, "+233200000001"), (no, "+233200000002")):
        row = await db_session.get(m.GymMember, mem["id"])
        row.phone = phone
        await _sell(ac, h, mem, plan)
    await db_session.commit()
    assert (await ac.post(f"/api/v1/gym/members/{yes['id']}/consent", headers=h, json={"consent": True})).status_code == 200
    camp = (await ac.post("/api/v1/gym/campaigns", headers=h, json={"name": "Bring a friend", "channel": "sms", "audience": "active", "message": "Hi {name}, bring a friend free this week."})).json()["data"]
    sent = await ac.post(f"/api/v1/gym/campaigns/{camp['id']}/send", headers=h)
    assert sent.status_code == 200, sent.text
    counts = sent.json()["data"]["counts"]
    assert counts.get("skipped") == 1 and (counts.get("sent", 0) + counts.get("failed", 0)) == 1
    recips = (await ac.get(f"/api/v1/gym/campaigns/{camp['id']}/recipients", headers=h)).json()["data"]
    assert any(r["detail"] == "Has not agreed to marketing" for r in recips)
    assert (await ac.post(f"/api/v1/gym/campaigns/{camp['id']}/send", headers=h)).status_code == 409
    # withdrawing consent works and is audited
    assert (await ac.post(f"/api/v1/gym/members/{yes['id']}/consent", headers=h, json={"consent": False})).json()["data"]["marketing_consent"] is False


@pytest.mark.asyncio
async def test_only_renewal_reminders_may_skip_consent_and_email_needs_a_subject(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    promo = {"name": "Sale", "channel": "sms", "audience": "active", "kind": "service", "message": "Big sale"}
    assert (await ac.post("/api/v1/gym/campaigns", headers=h, json=promo)).status_code == 422
    assert (await ac.post("/api/v1/gym/campaigns", headers=h, json={"name": "News", "channel": "email", "audience": "leads", "message": "Hello"})).status_code == 422
    ok = {"name": "Renew", "channel": "sms", "audience": "expiring", "kind": "service", "message": "Your plan ends soon, {name}."}
    assert (await ac.post("/api/v1/gym/campaigns", headers=h, json=ok)).status_code == 200


@pytest.mark.asyncio
async def test_crm_is_tenant_scoped_role_limited_and_gym_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    theirs = m.GymLead(tenant_id=seed["t2"].id, full_name="Theirs", phone="+233200000009", status="new")
    camp = m.GymCampaign(tenant_id=seed["t2"].id, name="X", channel="sms", audience="active", message="hi")
    other = m.GymMember(tenant_id=seed["t2"].id, member_number="GM-1", full_name="T", joined_on=date.today())
    db_session.add_all([theirs, camp, other])
    await db_session.commit()
    assert (await ac.post(f"/api/v1/gym/leads/{theirs.id}/convert", headers=h)).status_code == 404
    assert (await ac.post(f"/api/v1/gym/campaigns/{camp.id}/send", headers=h)).status_code == 404
    assert (await ac.get(f"/api/v1/gym/campaigns/{camp.id}/recipients", headers=h)).status_code == 404
    assert (await ac.post(f"/api/v1/gym/members/{other.id}/consent", headers=h, json={"consent": True})).status_code == 404
    assert (await ac.get("/api/v1/gym/leads", headers=h)).json()["data"] == []
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/gym/campaigns", headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_renewal_reminders_reach_only_members_whose_plan_ends_soon_once_a_day(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    short, long_ = await _plan(ac, h, days=3), await _plan(ac, h, days=60)
    soon, later, noone = await _member(ac, h), await _member(ac, h), await _member(ac, h)
    for mem, phone in ((soon, "+233200000011"), (later, "+233200000012")):
        row = await db_session.get(m.GymMember, mem["id"])
        row.phone = phone
    await db_session.commit()
    await _sell(ac, h, soon, short)
    await _sell(ac, h, later, long_)
    res = await ac.post("/api/v1/gym/reminders/run", headers=h, json={"channel": "sms"})
    assert res.status_code == 200, res.text
    camp = res.json()["data"]
    assert camp["kind"] == "service" and sum(camp["counts"].values()) == 1  # only the member whose plan ends soon
    assert (await ac.post("/api/v1/gym/reminders/run", headers=h, json={"channel": "sms"})).status_code == 409
    assert (await ac.post("/api/v1/gym/reminders/run", headers=h, json={"channel": "email"})).status_code == 200
    assert (await ac.post("/api/v1/gym/reminders/run", headers=h, json={"channel": "push"})).status_code == 422
    assert noone["id"]


@pytest.mark.asyncio
async def test_the_daily_reminder_job_is_off_until_a_manager_turns_it_on(client, seeded, db_session):
    from app import jobs as jobs_svc

    ac, seed = client
    h = await _admin(ac, seed, db_session)
    assert (await ac.get("/api/v1/gym/reminders/auto", headers=h)).json()["data"]["reminder_channels"] == ""
    assert (await ac.post("/api/v1/gym/reminders/auto", headers=h, json={"channels": "whatsapp"})).status_code == 422
    assert "send_gym_renewal_reminders" in jobs_svc.JOB_HANDLERS
    assert (await ac.post("/api/v1/gym/reminders/auto", headers=h, json={"channels": "sms"})).status_code == 200
    assert (await ac.get("/api/v1/gym/reminders/auto", headers=h)).json()["data"]["reminder_channels"] == "sms"
    assert (await ac.post("/api/v1/gym/reminders/auto", headers=h, json={"channels": ""})).status_code == 200
