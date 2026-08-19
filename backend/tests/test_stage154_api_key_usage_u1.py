"""Stage 154 U1 — API key usage CSV export."""

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
async def test_api_key_usage_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)
    created = await ac.post(
        "/api/v1/api-keys",
        headers=headers,
        json={"name": "Stage 154 Usage Key"},
    )
    assert created.status_code == 200, created.text
    key_id = created.json()["data"]["id"]
    # Ensure raw secret is not leaked into usage export
    raw = created.json()["data"].get("api_key") or created.json()["data"].get("raw_key")
    exported = await ac.get(
        f"/api/v1/api-keys/{key_id}/usage/export?days=30",
        headers=headers,
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "usage_date" in header and "requests" in header
    assert "summary" in text
    assert "key_prefix" in text
    if raw:
        assert raw not in text


def test_api_key_usage_export_ui_u1():
    page = (ROOT / "frontend/app/security/page.tsx").read_text(encoding="utf-8")
    assert "Stage 154" in page
    assert "/usage/export" in page
    assert "Export usage CSV" in page
