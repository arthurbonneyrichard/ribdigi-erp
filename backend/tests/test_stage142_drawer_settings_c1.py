"""Stage 142 C1 — store cash drawer settings CSV (kick bytes never included)."""

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
async def test_drawer_settings_export_csv_secret_free(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    store = seed["store1"]

    patched = await ac.patch(
        f"/api/v1/stores/{store.id}/drawer",
        headers=headers,
        json={
            "drawer_mode": "network",
            "drawer_host": "10.0.0.42",
            "drawer_port": 9100,
            "drawer_open_on_cash": True,
        },
    )
    assert patched.status_code == 200, patched.text

    exported = await ac.get("/api/v1/stores/drawer-settings/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "drawer_mode" in header and "drawer_host" in header and "store_id" in header
    assert store.id in text
    assert "network" in text
    assert "10.0.0.42" in text
    lower = text.lower()
    assert "kick" not in lower
    assert "base64" not in lower
    assert "\\x1b" not in lower
    assert "escpos" not in lower.replace("-", "").replace("_", "")


def test_drawer_settings_export_ui_c1():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Stage 142" in page
    assert "/stores/drawer-settings/export" in page
    assert "Export drawer settings CSV" in page
    assert "cash-drawer" in page
