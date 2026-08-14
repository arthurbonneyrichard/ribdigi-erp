"""Tenant-editable SMTP settings (BR-20.3)."""

from __future__ import annotations

from types import SimpleNamespace

import pyotp
import pytest

from app import emailer
from app.email_settings import apply_email_settings_update, resolve_smtp_config
from app.totp import encrypt_secret
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_resolve_prefers_tenant_over_env(monkeypatch):
    monkeypatch.setattr("app.email_settings.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.email_settings.settings.SMTP_HOST", "env.example.com")
    monkeypatch.setattr("app.email_settings.settings.SMTP_FROM_EMAIL", "env@example.com")
    monkeypatch.setattr("app.email_settings.settings.SMTP_PASSWORD", "env-secret")
    tenant = SimpleNamespace(
        email_settings={
            "host": "tenant.smtp.test",
            "port": 465,
            "username": "tenant-user",
            "password_enc": encrypt_secret("tenant-secret"),
            "from_email": "noreply@tenant.test",
            "from_name": "Tenant Mail",
            "use_tls": False,
            "use_ssl": True,
        }
    )
    cfg = resolve_smtp_config(tenant)
    assert cfg.source == "tenant"
    assert cfg.host == "tenant.smtp.test"
    assert cfg.port == 465
    assert cfg.password == "tenant-secret"
    assert cfg.from_email == "noreply@tenant.test"
    assert cfg.use_ssl is True


def test_apply_encrypts_password_and_status_hides_it():
    tenant = SimpleNamespace(email_settings=None)
    status = apply_email_settings_update(
        tenant,
        {
            "host": "smtp.example.com",
            "port": 587,
            "username": "u",
            "password": "s3cret",
            "from_email": "from@example.com",
            "from_name": "ERP",
            "use_tls": True,
            "use_ssl": False,
        },
    )
    assert "password" not in status
    assert "password_enc" not in status
    assert status["has_password"] is True
    assert status["tenant_override"] is True
    assert status["source"] == "tenant"
    assert "password_enc" in tenant.email_settings
    assert tenant.email_settings["password_enc"] != "s3cret"


@pytest.mark.asyncio
async def test_patch_email_settings_api_no_password_leak(client):
    ac, seed = client
    admin = await _super(ac, seed)
    patched = await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={
            "host": "mail.alpha.test",
            "port": 587,
            "username": "alpha",
            "password": "AlphaSmtpPass!",
            "from_email": "noreply@alpha.test",
            "from_name": "Alpha ERP",
            "use_tls": True,
            "use_ssl": False,
        },
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()["data"]
    assert data["host"] == "mail.alpha.test"
    assert data["from_email"] == "noreply@alpha.test"
    assert data["tenant_override"] is True
    assert data["has_password"] is True
    assert data.get("password") in (None, "")
    assert "password_enc" not in patched.text.lower()
    assert "AlphaSmtpPass" not in patched.text

    got = await ac.get("/api/v1/settings/email", headers=admin)
    assert got.status_code == 200, got.text
    body = got.json()["data"]
    assert body["source"] == "tenant"
    assert body["has_password"] is True
    assert "password" not in body or body.get("password") in (None, "")


@pytest.mark.asyncio
async def test_test_email_uses_tenant_config(client, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    monkeypatch.setattr("app.email_settings.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.emailer.settings.EMAIL_ENABLED", True)
    monkeypatch.setattr("app.email_settings.settings.SMTP_HOST", "")
    monkeypatch.setattr("app.emailer.settings.SMTP_HOST", "")

    await ac.patch(
        "/api/v1/settings/email",
        headers=admin,
        json={
            "host": "tenant-only.smtp",
            "port": 587,
            "from_email": "from@tenant-only.test",
            "from_name": "Tenant Only",
        },
    )

    captured: list = []

    def fake_send(msg, cfg):
        captured.append((msg["From"], cfg.host, cfg.from_email, cfg.source))

    monkeypatch.setattr("app.emailer._smtp_send_sync", fake_send)
    emailer.clear_dev_outbox()
    r = await ac.post("/api/v1/settings/email/test", headers=admin, json={})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["sent"] is True
    assert r.json()["data"]["mode"] == "smtp"
    assert len(captured) == 1
    assert captured[0][1] == "tenant-only.smtp"
    assert captured[0][2] == "from@tenant-only.test"
    assert captured[0][3] == "tenant"
