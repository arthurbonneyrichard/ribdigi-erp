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
