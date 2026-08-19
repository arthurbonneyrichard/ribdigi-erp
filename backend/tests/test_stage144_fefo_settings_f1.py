"""Stage 144 F1 — inventory FEFO settings CSV export."""

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
async def test_fefo_settings_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)

    patched = await ac.patch(
        "/api/v1/inventory/settings",
        headers=headers,
        json={"fefo_strict_warehouse": True},
    )
    assert patched.status_code == 200, patched.text

    exported = await ac.get("/api/v1/inventory/settings/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "fefo_strict_warehouse" in header
    assert "true" in text.lower()


def test_fefo_settings_export_ui_f1():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Stage 144" in page
    assert "/inventory/settings/export" in page
    assert "Export FEFO settings CSV" in page
    assert 'id="fefo"' in page
