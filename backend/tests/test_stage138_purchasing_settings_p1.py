"""Stage 138 P1 — purchasing approval settings CSV export."""

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
async def test_purchasing_settings_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    current = await ac.get("/api/v1/purchasing/settings", headers=headers)
    assert current.status_code == 200, current.text
    data = current.json()["data"]
    levels = data["levels"]
    assert levels

    exported = await ac.get("/api/v1/purchasing/settings/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "l1_threshold" in header
    assert "l2_threshold" in header
    assert "levels_count" in header
    assert "levels_json" in header
    assert "max_levels" in header
    assert str(len(levels)) in text
    assert "levels_json" in text


def test_purchasing_settings_export_ui_p1():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 138" in page
    assert "/purchasing/settings/export" in page
    assert "Export approval settings CSV" in page
