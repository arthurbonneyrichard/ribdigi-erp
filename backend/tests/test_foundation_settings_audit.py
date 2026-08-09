"""Tenant SMTP settings + audit PDF export."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_tenant_smtp_settings_and_formats(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)

    status = await ac.get("/api/v1/settings/email", headers=headers)
    assert status.status_code == 200, status.text
    body = status.json()["data"]
    assert "source" in body
    assert "tenant_override_enabled" in body

    saved = await ac.patch(
        "/api/v1/settings/email",
        headers=headers,
        json={
            "smtp_enabled": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "mailer",
            "smtp_password": "secret-pass",
            "smtp_from_email": "noreply@alpha.example.com",
            "smtp_from_name": "Alpha ERP",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["source"] == "tenant"
    assert data["host"] == "smtp.example.com"
    assert data["from_email"] == "noreply@alpha.example.com"
    assert data["has_password"] is True
    assert data["tenant_override_enabled"] is True

    profile = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "date_format": "YYYY-MM-DD",
            "number_format": "1.234,56",
            "time_format": "12h",
        },
    )
    assert profile.status_code == 200, profile.text
    pdata = profile.json()["data"]
    assert pdata["date_format"] == "YYYY-MM-DD"
    assert pdata["number_format"] == "1.234,56"
    assert pdata["time_format"] == "12h"


@pytest.mark.asyncio
async def test_audit_export_pdf(client):
    ac, seed = client
    headers = await _admin_headers(ac, seed)
    # Ensure at least one audit event exists via a harmless settings read is not audited;
    # use email test which records an audit event.
    await ac.post("/api/v1/settings/email/test", headers=headers, json={})
    export = await ac.get("/api/v1/audit-logs/export?format=pdf", headers=headers)
    assert export.status_code == 200, export.text
    assert export.headers.get("content-type", "").startswith("application/pdf")
    assert export.content[:4] == b"%PDF"
