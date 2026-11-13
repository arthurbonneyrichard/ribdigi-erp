"""Email center: the software owner emails company admins, one message per person."""

from __future__ import annotations

import pytest

from app import emailer
from app import models as m
from app.db import SessionLocal  # noqa: F401  (patched by the client fixture)
from app.security import hash_password
from tests.conftest import auth_headers, platform_owner_headers

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _console_email(monkeypatch):
    emailer.clear_dev_outbox()
    for mod in ("app.email_settings.settings", "app.emailer.settings"):
        monkeypatch.setattr(f"{mod}.EMAIL_ENABLED", True)
        monkeypatch.setattr(f"{mod}.SMTP_HOST", "")
        monkeypatch.setattr(f"{mod}.SMTP_FROM_EMAIL", "noreply@localhost")
    yield
    emailer.clear_dev_outbox()


async def _add_beta_admin(seed) -> None:
    from app import db as db_mod

    async with db_mod.SessionLocal() as db:
        db.add(
            m.User(
                tenant_id=seed["t2"].id,
                email="Boss@Beta.example.com",
                full_name="Beta Boss",
                role="company_admin",
                password_hash=hash_password("SecurePass123!"),
                is_active=True,
            )
        )
        beta = await db.get(m.Tenant, seed["t2"].id)
        beta.email = "office@beta.example.com"
        await db.commit()


async def test_owner_previews_tests_and_sends_to_company_admins(client):
    ac, seed = client
    await _add_beta_admin(seed)
    owner = await platform_owner_headers(ac, seed)

    status = await ac.get("/api/v1/platform/email/status", headers=owner)
    assert status.status_code == 200, status.text
    assert status.json()["data"]["from_name"]
    assert status.json()["data"]["from_email"] == "noreply@localhost"

    preview = await ac.post("/api/v1/platform/email/preview", json={}, headers=owner)
    assert preview.status_code == 200, preview.text
    data = preview.json()["data"]
    emails = [row["email"] for row in data["sample"]]
    # The owner's own company is left out; beta's admin is in, lower-cased.
    assert emails == ["boss@beta.example.com"]
    assert data["company_count"] == 1

    with_office = await ac.post(
        "/api/v1/platform/email/preview", json={"include_company_email": True}, headers=owner
    )
    assert with_office.json()["data"]["recipient_count"] == 2

    none = await ac.post("/api/v1/platform/email/preview", json={"statuses": ["suspended"]}, headers=owner)
    assert none.json()["data"]["recipient_count"] == 0

    bad = await ac.post("/api/v1/platform/email/preview", json={"statuses": ["gone"]}, headers=owner)
    assert bad.status_code == 422

    message = {"subject": "News for {company_name}", "body": "Hello {company_name},\n\nWe added reports to Starter."}
    test = await ac.post("/api/v1/platform/email/test", json={**message, "to": "me@example.com"}, headers=owner)
    assert test.status_code == 200, test.text
    assert emailer.get_dev_outbox()[-1]["to"] == ["me@example.com"]
    emailer.clear_dev_outbox()

    unconfirmed = await ac.post("/api/v1/platform/email/send", json=message, headers=owner)
    assert unconfirmed.status_code == 422

    sent = await ac.post(
        "/api/v1/platform/email/send", json={**message, "include_company_email": True, "confirm": True}, headers=owner
    )
    assert sent.status_code == 200, sent.text
    outbox = emailer.get_dev_outbox()
    assert sorted(row["to"][0] for row in outbox) == ["boss@beta.example.com", "office@beta.example.com"]
    # One message per person, with the company name filled in.
    assert all(len(row["to"]) == 1 for row in outbox)
    assert all(row["subject"] == "News for Beta Co" for row in outbox)
    assert "{company_name}" not in outbox[0]["text_body"]

    history = await ac.get("/api/v1/platform/email/history", headers=owner)
    assert history.status_code == 200, history.text
    rows = history.json()["data"]
    assert rows[0]["subject"] == "News for {company_name}"
    assert rows[0]["recipient_count"] == 2
    assert rows[0]["status"] == "finished"
    assert rows[0]["sent"] == 2 and rows[0]["failed"] == 0


async def test_company_admin_cannot_use_the_email_center(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.post("/api/v1/platform/email/preview", json={}, headers=admin)
    assert r.status_code == 403


async def test_send_refuses_when_email_is_off(client, monkeypatch):
    ac, seed = client
    await _add_beta_admin(seed)
    owner = await platform_owner_headers(ac, seed)
    monkeypatch.setattr("app.email_settings.settings.EMAIL_ENABLED", False)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", False)
    r = await ac.post(
        "/api/v1/platform/email/send",
        json={"subject": "Hi", "body": "Hello there", "confirm": True},
        headers=owner,
    )
    assert r.status_code == 503
    assert emailer.get_dev_outbox() == []


async def test_pick_companies_render_open_and_retry(client, monkeypatch):
    from app import platform_email as svc

    ac, seed = client
    await _add_beta_admin(seed)
    owner = await platform_owner_headers(ac, seed)

    companies = await ac.get("/api/v1/platform/email/companies", headers=owner)
    assert companies.status_code == 200, companies.text
    rows = companies.json()["data"]
    beta = next(row for row in rows if row["id"] == seed["t2"].id)
    assert beta["company_name"] == "Beta Co"

    picked = await ac.post(
        "/api/v1/platform/email/preview",
        json={"tenant_ids": [beta["id"]], "include_company_email": True},
        headers=owner,
    )
    assert picked.json()["data"]["recipient_count"] == 2
    bad_pick = await ac.post("/api/v1/platform/email/preview", json={"tenant_ids": ["beta"]}, headers=owner)
    assert bad_pick.status_code == 422

    shown = await ac.post(
        "/api/v1/platform/email/render",
        json={"subject": "Hi {company_name}", "body": "Hello {company_name}", "company_name": "Beta Co"},
        headers=owner,
    )
    assert shown.status_code == 200, shown.text
    assert shown.json()["data"]["subject"] == "Hi Beta Co"
    assert "Hello Beta Co" in shown.json()["data"]["html"]

    # The office address bounces the first time.
    real_send_one = svc.send_one

    async def flaky(email, subject, body, company_name):
        if email == "office@beta.example.com":
            return False, "mailbox full"
        return await real_send_one(email, subject, body, company_name)

    monkeypatch.setattr(svc, "send_one", flaky)
    long_body = "Hello {company_name},\n\n" + ("All the news. " * 60)
    sent = await ac.post(
        "/api/v1/platform/email/send",
        json={"subject": "News", "body": long_body, "tenant_ids": [beta["id"]],
              "include_company_email": True, "confirm": True},
        headers=owner,
    )
    assert sent.status_code == 200, sent.text
    send_id = sent.json()["data"]["id"]

    detail = await ac.get(f"/api/v1/platform/email/history/{send_id}", headers=owner)
    assert detail.status_code == 200, detail.text
    d = detail.json()["data"]
    assert d["body"] == long_body.strip() and d["body_complete"] is True
    assert d["sent"] == 1 and d["failed"] == 1
    assert d["failures"][0]["company_name"] == "Beta Co"
    assert d["filters"]["tenant_ids"] == [beta["id"]]

    monkeypatch.setattr(svc, "send_one", real_send_one)
    emailer.clear_dev_outbox()
    unconfirmed = await ac.post(f"/api/v1/platform/email/history/{send_id}/retry", json={}, headers=owner)
    assert unconfirmed.status_code == 422
    retry = await ac.post(f"/api/v1/platform/email/history/{send_id}/retry", json={"confirm": True}, headers=owner)
    assert retry.status_code == 200, retry.text
    outbox = emailer.get_dev_outbox()
    assert [row["to"][0] for row in outbox] == ["office@beta.example.com"]
    assert outbox[0]["subject"] == "News"
    assert "Hello Beta Co" in outbox[0]["text_body"]

    history = (await ac.get("/api/v1/platform/email/history", headers=owner)).json()["data"]
    assert history[0]["filters"]["retry_of"] == send_id
    assert history[0]["sent"] == 1 and history[0]["failed"] == 0
    assert "body" not in history[0]

    nothing_left = await ac.post(
        f"/api/v1/platform/email/history/{history[0]['id']}/retry", json={"confirm": True}, headers=owner
    )
    assert nothing_left.status_code == 409
    missing = await ac.get("/api/v1/platform/email/history/00000000-0000-0000-0000-000000000000", headers=owner)
    assert missing.status_code == 404


async def test_send_without_a_finish_is_shown_as_stopped(client):
    from datetime import datetime, timedelta

    from app import db as db_mod
    from app import platform_email as svc

    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    me = (await ac.get("/api/v1/me", headers=owner)).json()["data"]
    tenant_id = me.get("tenant_id") or me.get("tenant", {}).get("id")
    async with db_mod.SessionLocal() as db:
        send_id = await svc.record_start(
            db,
            actor={"tenant_id": tenant_id, "user_id": None, "email": None},
            subject="Cut off",
            body="Hello there",
            filters={},
            summary={"recipient_count": 3, "company_count": 1},
        )
        await db.commit()
        row = (
            await db.execute(
                svc.select(m.AuditLog).where(m.AuditLog.entity_id == send_id)
            )
        ).scalar_one()
        row.created_at = datetime.utcnow() - timedelta(hours=2)
        await db.commit()
    history = (await ac.get("/api/v1/platform/email/history", headers=owner)).json()["data"]
    assert history[0]["id"] == send_id and history[0]["status"] == "stopped"
    retry = await ac.post(f"/api/v1/platform/email/history/{send_id}/retry", json={"confirm": True}, headers=owner)
    assert retry.status_code == 409
