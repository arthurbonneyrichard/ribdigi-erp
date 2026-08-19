"""Stage 131 E1 — email settings CSV export (secret-free)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    return await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_email_settings_export_csv_secret_free(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)

    # Persist a tenant SMTP override with a real password; export must never echo it.
    patched = await ac.patch(
        "/api/v1/settings/email",
        headers=headers,
        json={
            "smtp_enabled": True,
            "smtp_host": "smtp.stage131.example",
            "smtp_port": 587,
            "smtp_username": "stage131-user",
            "smtp_password": "SuperSecretPassword131!",
            "smtp_from_email": "noreply@stage131.example",
            "smtp_from_name": "Stage131",
            "smtp_use_tls": True,
            "smtp_use_ssl": False,
        },
    )
    assert patched.status_code == 200, patched.text

    exported = await ac.get("/api/v1/settings/email/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "has_password" in header
    assert "host" in header and "from_email" in header
    assert "smtp_password" not in header
    assert "password" not in [c.strip() for c in header.split(",")]
    assert "SuperSecretPassword131!" not in text
    assert "smtp.stage131.example" in text
    assert "True" in text or "true" in text.lower()


@pytest.mark.asyncio
async def test_email_settings_export_requires_admin(client):
    ac, seed = client
    cashier = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    denied = await ac.get("/api/v1/settings/email/export", headers=cashier)
    assert denied.status_code in (401, 403), denied.text


def test_company_email_export_ui_e1():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 131" in page
    assert "/settings/email/export" in page
    assert "Export email settings CSV" in page
