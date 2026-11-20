"""FMCG alerts: expiry bands, vehicle documents, once per band, who is told and how."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from app import emailer, fmcg_alerts
from app import models as m
from app import sms as sms_svc
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"


@pytest.fixture
def sent(monkeypatch):
    box = {"email": [], "sms": []}

    async def fake_email(*, to, title, message, category, tenant=None, **_):
        box["email"].append((to, category, title))

    async def fake_sms(*, to, title, message, tenant=None, **_):
        box["sms"].append((to, title))

    monkeypatch.setattr(emailer, "send_notification_email", fake_email)
    monkeypatch.setattr(sms_svc, "send_notification_sms", fake_sms)
    return box


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _staff(db_session, seed, role, phone=None):
    u = m.User(tenant_id=seed["t1"].id, email=f"{role}@alpha.example.com", full_name=role, password_hash=hash_password("SecurePass123!"),
               role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False, phone=phone)
    db_session.add(u)
    await db_session.commit()
    return u


async def _batch(db_session, seed, days, qty=20, number="B1"):
    p = m.Product(tenant_id=seed["t1"].id, name=f"Milk {uuid4().hex[:4]}", sku=f"M{uuid4().hex[:7]}", cost_price=5, selling_price=9,
                  stock_qty=qty, is_active=True, tracks_batches=True)
    db_session.add(p)
    await db_session.flush()
    b = m.ProductBatch(tenant_id=seed["t1"].id, product_id=p.id, batch_number=number, quantity=qty, expiry_date=datetime.utcnow() + timedelta(days=days, hours=1))
    db_session.add(b)
    await db_session.flush()
    bid = b.id
    await db_session.commit()
    return SimpleNamespace(id=bid)


async def _set_expiry(db_session, batch_id, days, hours=1):
    await db_session.execute(update(m.ProductBatch).where(m.ProductBatch.id == batch_id).values(expiry_date=datetime.utcnow() + timedelta(days=days, hours=hours)))
    await db_session.commit()


async def _notes(db_session, category):
    db_session.expire_all()
    return (await db_session.execute(select(m.Notification).where(m.Notification.category == category))).scalars().all()


def test_bands():
    w = [90, 60, 30, 14, 7]
    assert fmcg_alerts.band_for(100, w) is None and fmcg_alerts.band_for(90, w) == 90 and fmcg_alerts.band_for(45, w) == 60
    assert fmcg_alerts.band_for(30, w) == 30 and fmcg_alerts.band_for(8, w) == 14 and fmcg_alerts.band_for(0, w) == 7
    assert fmcg_alerts.band_for(-1, w) == 0 and fmcg_alerts.band_for(None, w) is None and fmcg_alerts.band_for(5, [10]) == 10


@pytest.mark.asyncio
async def test_each_band_alerts_once_even_if_the_alert_is_deleted(client, seeded, db_session, sent):
    ac, seed = client
    await _admin(ac, seed, db_session)
    b = await _batch(db_session, seed, days=50)  # band 60
    assert (await fmcg_alerts.scan(db_session, seed["t1"].id))["batch"] == 1
    await db_session.commit()
    assert (await fmcg_alerts.scan(db_session, seed["t1"].id))["batch"] == 0
    await db_session.execute(m.Notification.__table__.delete().where(m.Notification.category == "batch_expiry"))  # read and deleted: still no repeat
    await db_session.commit()
    assert (await fmcg_alerts.scan(db_session, seed["t1"].id))["batch"] == 0
    # Closer to expiry: the next tighter band alerts once.
    await _set_expiry(db_session, b.id, 10)
    assert (await fmcg_alerts.scan(db_session, seed["t1"].id))["batch"] == 1  # band 14
    await db_session.commit()
    assert (await fmcg_alerts.scan(db_session, seed["t1"].id))["batch"] == 0
    await _set_expiry(db_session, b.id, -2)
    assert (await fmcg_alerts.scan(db_session, seed["t1"].id))["batch"] == 1  # expired
    notes = await _notes(db_session, "batch_expiry")
    assert any("expired" in n.title.lower() for n in notes)
    log = (await ac.get(f"{API}/alerts/log", headers=await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha"))).json()["data"]
    assert sorted(x["band"] for x in log) == [0, 14, 60]


@pytest.mark.asyncio
async def test_company_warning_days_decide_what_is_alerted(client, seeded, db_session, sent):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    tid = seed["t1"].id
    await _batch(db_session, seed, days=20)
    assert (await ac.put(f"{API}/batch-policy", headers=h, json={"warn_days": [5]})).status_code == 200
    db_session.expire_all()  # the scan job opens a fresh session; the test session must not keep the old company record
    assert (await fmcg_alerts.scan(db_session, tid))["batch"] == 0  # 20 days is outside a 5 day window
    far = await _batch(db_session, seed, days=400, number="FAR")
    assert (await fmcg_alerts.scan(db_session, tid))["batch"] == 0
    await _set_expiry(db_session, far.id, 4)
    assert (await fmcg_alerts.scan(db_session, tid))["batch"] == 1
    empty = await _batch(db_session, seed, days=-3, qty=1, number="EMPTY")
    await db_session.execute(update(m.ProductBatch).where(m.ProductBatch.id == empty.id).values(quantity=0))
    await db_session.commit()
    assert (await fmcg_alerts.scan(db_session, tid))["batch"] == 0  # nothing left to lose


@pytest.mark.asyncio
async def test_vehicle_documents_alert_by_band(client, seeded, db_session, sent):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    d = lambda n: (date.today() + timedelta(days=n)).isoformat()
    soon = (await ac.post(f"{API}/fleet/vehicles", headers=h, json={"plate": "GR 1-26", "name": "Van A", "insurance_expiry": d(20), "roadworthy_expiry": d(200), "licence_expiry": d(-1)})).json()["data"]
    await ac.post(f"{API}/fleet/vehicles", headers=h, json={"plate": "GR 2-26", "name": "Van B"})  # nothing recorded: nothing to say
    retired = (await ac.post(f"{API}/fleet/vehicles", headers=h, json={"plate": "GR 3-26", "name": "Van C", "insurance_expiry": d(-5)})).json()["data"]
    await ac.patch(f"{API}/fleet/vehicles/{retired['id']}", headers=h, json={"status": "retired"})
    assert (await fmcg_alerts.scan(db_session, seed["t1"].id))["vehicle"] == 2  # insurance within 30, licence expired
    await db_session.commit()
    assert (await fmcg_alerts.scan(db_session, seed["t1"].id))["vehicle"] == 0
    titles = [n.title for n in await _notes(db_session, "fleet_document")]
    assert "GR 1-26: licence expired" in titles and "GR 1-26: insurance expiring within 30 days" in titles
    assert not any("GR 3-26" in t for t in titles)


@pytest.mark.asyncio
async def test_right_people_get_email_and_only_opted_in_people_get_sms(client, seeded, db_session, sent):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    store = await _staff(db_session, seed, "fmcg_storekeeper", phone="+233201111111")
    qc = await _staff(db_session, seed, "fmcg_quality", phone="+233202222222")
    fleet = await _staff(db_session, seed, "fmcg_fleet", phone="+233203333333")
    rep = await _staff(db_session, seed, "fmcg_rep", phone="+233204444444")
    driver = await _staff(db_session, seed, "fmcg_driver", phone="+233205555555")
    # The storekeeper switches SMS on for expiry; the fleet manager for vehicle papers; nobody else does.
    sk = await auth_headers(ac, email="fmcg_storekeeper@alpha.example.com", tenant_slug="alpha")
    fl = await auth_headers(ac, email="fmcg_fleet@alpha.example.com", tenant_slug="alpha")
    assert (await ac.patch("/api/v1/notifications/settings", headers=sk, json={"preferences": {"batch_expiry": {"sms": True}}})).status_code == 200
    assert (await ac.patch("/api/v1/notifications/settings", headers=fl, json={"preferences": {"fleet_document": {"sms": True}}})).status_code == 200
    await _batch(db_session, seed, days=3)
    await ac.post(f"{API}/fleet/vehicles", headers=h, json={"plate": "GR 9-26", "name": "Van Z", "roadworthy_expiry": (date.today() + timedelta(days=5)).isoformat()})
    sent["email"].clear()
    sent["sms"].clear()
    assert await fmcg_alerts.scan(db_session, seed["t1"].id) == {"batch": 1, "vehicle": 1}
    mail = {(to, cat) for to, cat, _ in sent["email"]}
    assert ("fmcg_storekeeper@alpha.example.com", "batch_expiry") in mail and ("fmcg_quality@alpha.example.com", "batch_expiry") in mail
    assert ("fmcg_fleet@alpha.example.com", "fleet_document") in mail and ("admin@alpha.example.com", "batch_expiry") in mail
    assert not any(to in ("fmcg_rep@alpha.example.com", "fmcg_driver@alpha.example.com") for to, _, _ in sent["email"])
    assert ("fmcg_fleet@alpha.example.com", "batch_expiry") not in mail  # the fleet manager is not told about stock
    phones = {to for to, _ in sent["sms"]}
    assert phones == {"+233201111111", "+233203333333"}  # only those who switched SMS on and have a number


@pytest.mark.asyncio
async def test_scan_only_runs_for_fmcg_companies_and_is_manager_only(client, seeded, db_session, sent):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _batch(db_session, seed, days=3)
    assert (await ac.post(f"{API}/alerts/scan", headers=h)).json()["data"]["batch"] == 1
    assert (await ac.post(f"{API}/alerts/scan", headers=h)).json()["data"]["batch"] == 0
    await _staff(db_session, seed, "fmcg_rep")
    rep = await auth_headers(ac, email="fmcg_rep@alpha.example.com", tenant_slug="alpha")
    assert (await ac.post(f"{API}/alerts/scan", headers=rep)).status_code == 403
    assert (await ac.get(f"{API}/alerts/log", headers=rep)).status_code == 403
    await set_tenant_industry(db_session, seed["t2"], "retail")
    out = await fmcg_alerts.scan(db_session, seed["t2"].id)
    assert out["batch"] == 0 and out["vehicle"] == 0 and "skipped" in out
    # Another company's expiring batch is never alerted into this company's log.
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    log = (await ac.get(f"{API}/alerts/log", headers=h)).json()["data"]
    assert len(log) == 1
