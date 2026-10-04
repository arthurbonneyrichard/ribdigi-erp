"""Tenant-editable Twilio SMS settings."""

from __future__ import annotations

from types import SimpleNamespace

import pyotp
import pytest

from app import sms as sms_svc
from app.sms_settings import apply_sms_settings_update, resolve_sms_config
from app.totp import encrypt_secret
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_resolve_prefers_tenant_over_env(monkeypatch):
    monkeypatch.setattr("app.sms_settings.settings.SMS_ENABLED", True)
    monkeypatch.setattr("app.sms_settings.settings.TWILIO_ACCOUNT_SID", "ACenv")
    monkeypatch.setattr("app.sms_settings.settings.TWILIO_AUTH_TOKEN", "env-token")
    monkeypatch.setattr("app.sms_settings.settings.TWILIO_FROM_NUMBER", "+15550001111")
    tenant = SimpleNamespace(
        sms_settings={
            "account_sid": "ACtenant",
            "auth_token_enc": encrypt_secret("tenant-token"),
            "from_number": "+233241111111",
        }
    )
    cfg = resolve_sms_config(tenant)
    assert cfg.source == "tenant"
    assert cfg.account_sid == "ACtenant"
    assert cfg.auth_token == "tenant-token"
    assert cfg.from_number == "+233241111111"
    assert cfg.configured is True


def test_apply_encrypts_token_and_status_hides_it():
    tenant = SimpleNamespace(sms_settings=None)
    status = apply_sms_settings_update(
        tenant,
        {
            "account_sid": "ACxxxx",
            "auth_token": "secret-token",
            "from_number": "+233200000001",
        },
    )
    assert "auth_token" not in status
    assert "auth_token_enc" not in status
    assert status["has_auth_token"] is True
    assert status["tenant_override"] is True
    assert status["source"] == "tenant"
    assert "auth_token_enc" in tenant.sms_settings
    assert tenant.sms_settings["auth_token_enc"] != "secret-token"


@pytest.mark.asyncio
async def test_patch_sms_settings_api_no_token_leak(client):
    ac, seed = client
    admin = await _super(ac, seed)
    patched = await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={
            "account_sid": "ACalphaLive",
            "auth_token": "AlphaTwilioToken!",
            "from_number": "+233241000111",
        },
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()["data"]
    assert data["account_sid"] == "ACalphaLive"
    assert data["from_number"] == "+233241000111"
    assert data["tenant_override"] is True
    assert data["has_auth_token"] is True
    assert data.get("auth_token") in (None, "")
    assert "AlphaTwilioToken" not in patched.text
    assert "auth_token_enc" not in patched.text.lower()

    got = await ac.get("/api/v1/settings/sms", headers=admin)
    assert got.status_code == 200, got.text
    body = got.json()["data"]
    assert body["source"] == "tenant"
    assert body["has_auth_token"] is True
    assert "auth_token" not in body or body.get("auth_token") in (None, "")


@pytest.mark.asyncio
async def test_test_sms_uses_tenant_config(client, monkeypatch):
    ac, seed = client
    admin = await _super(ac, seed)
    monkeypatch.setattr("app.sms_settings.settings.SMS_ENABLED", True)
    monkeypatch.setattr("app.sms.settings.SMS_ENABLED", True)
    monkeypatch.setattr("app.sms_settings.settings.TWILIO_ACCOUNT_SID", "")
    monkeypatch.setattr("app.sms_settings.settings.TWILIO_AUTH_TOKEN", "")
    monkeypatch.setattr("app.sms_settings.settings.TWILIO_FROM_NUMBER", "")

    await ac.patch(
        "/api/v1/settings/sms",
        headers=admin,
        json={
            "account_sid": "ACtenantOnly",
            "auth_token": "tok",
            "from_number": "+233249999999",
        },
    )
    await ac.patch("/api/v1/me", headers=admin, json={"phone": "+233241234567"})

    captured: list = []

    class FakeResp:
        status_code = 201

        def json(self):
            return {"sid": "SMfake"}

        @property
        def text(self):
            return ""

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, data=None, auth=None):
            captured.append({"url": url, "data": data, "auth": auth})
            return FakeResp()

    monkeypatch.setattr("app.sms.httpx.AsyncClient", FakeClient)
    sms_svc.clear_dev_outbox()
    r = await ac.post("/api/v1/settings/sms/test", headers=admin, json={})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["sent"] is True
    assert r.json()["data"]["mode"] == "twilio"
    assert len(captured) == 1
    assert "ACtenantOnly" in captured[0]["url"]
    assert captured[0]["data"]["From"] == "+233249999999"
    assert captured[0]["auth"] == ("ACtenantOnly", "tok")
