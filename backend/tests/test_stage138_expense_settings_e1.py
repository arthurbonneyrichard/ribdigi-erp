"""Stage 138 E1 — expense approval settings CSV export."""

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
async def test_expense_settings_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    current = await ac.get("/api/v1/expenses/settings", headers=headers)
    assert current.status_code == 200, current.text
    levels = current.json()["data"]["levels"]
    assert levels

    exported = await ac.get("/api/v1/expenses/settings/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "expense_approval_threshold" in header
    assert "expense_l2_threshold" in header
    assert "levels_count" in header
    assert "levels_json" in header
    assert "max_levels" in header
    assert "levels_json" in text
    assert str(len(levels)) in text


def test_expense_settings_export_ui_e1():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Stage 138" in page
    assert "/expenses/settings/export" in page
    assert "Export approval settings CSV" in page
