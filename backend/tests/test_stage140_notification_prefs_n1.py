"""Stage 140 N1 — notification preferences CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_notification_prefs_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)

    current = await ac.get("/api/v1/notifications/settings", headers=headers)
    assert current.status_code == 200, current.text
    prefs = current.json()["data"]
    assert prefs

    exported = await ac.get("/api/v1/notifications/settings/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "category" in header
    assert "dashboard" in header and "email" in header and "sms" in header
    for cat in list(prefs.keys())[:3]:
        assert cat in text


def test_notification_prefs_export_ui_n1():
    page = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert "Stage 140" in page
    assert "/notifications/settings/export" in page
    assert "Export preferences CSV" in page
