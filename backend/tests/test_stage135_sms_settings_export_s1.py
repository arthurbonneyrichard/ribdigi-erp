"""Stage 135 S1 — SMS settings CSV export (secret-free)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    return await auth_headers(
        ac, email="admin@alpha.example.com", tenant_slug="alpha"
    )


@pytest.mark.asyncio
async def test_sms_settings_export_csv_secret_free(client, monkeypatch):
    ac, seed = client
    headers = await _admin(ac, seed)

    monkeypatch.setattr(
        "app.sms.sms_status",
        lambda: {
            "enabled": True,
            "configured": True,
            "mode": "twilio",
            "from_number": "+15551234567",
            "account_sid_set": True,
        },
    )
    # Ensure raw secrets are never present even if status somehow leaked them.
    monkeypatch.setattr(
        "app.config.settings.TWILIO_AUTH_TOKEN",
        "SuperSecretTwilioToken135!",
        raising=False,
    )

    exported = await ac.get("/api/v1/settings/sms/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "account_sid_set" in header
    assert "enabled" in header and "mode" in header
    assert "auth_token" not in header.lower()
    assert "account_sid," not in header and "account_sid\n" not in header
    assert "password" not in [c.strip().lower() for c in header.split(",")]
    assert "SuperSecretTwilioToken135!" not in text
    assert "True" in text or "true" in text.lower()
    assert "+15551234567" in text


@pytest.mark.asyncio
async def test_sms_settings_export_requires_admin(client):
    ac, seed = client
    cashier = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    denied = await ac.get("/api/v1/settings/sms/export", headers=cashier)
    assert denied.status_code in (401, 403), denied.text


def test_company_sms_export_ui_s1():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 135" in page
    assert "/settings/sms/export" in page
    assert "Export SMS settings CSV" in page
