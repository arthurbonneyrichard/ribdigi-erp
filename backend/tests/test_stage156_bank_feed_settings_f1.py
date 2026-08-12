"""Stage 156 F1 — secret-free bank-feed settings CSV export."""

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
async def test_bank_feed_settings_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)

    exported = await ac.get("/api/v1/settings/bank-feed/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "sync_enabled" in header
    assert "providers" in header
    assert "timeout_seconds" in header
    assert "celery_interval_minutes" in header
    # Never leak credentials / tokens in settings export
    lower = text.lower()
    assert "access_token" not in lower
    assert "password" not in lower
    assert "mock" in text or "http_json" in text


def test_bank_feed_settings_export_ui_f1():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 156" in page
    assert "/settings/bank-feed/export" in page
    assert "Export bank-feed settings CSV" in page
