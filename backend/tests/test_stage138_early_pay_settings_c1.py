"""Stage 138 C1 — early-pay settings CSV export."""

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
async def test_early_pay_settings_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    patched = await ac.patch(
        "/api/v1/credit/settings",
        headers=headers,
        json={"early_pay_discount_pct": 2.5, "early_pay_discount_days": 10},
    )
    assert patched.status_code == 200, patched.text

    exported = await ac.get("/api/v1/credit/settings/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "early_pay_discount_pct" in header
    assert "early_pay_discount_days" in header
    assert "enabled" in header
    assert "source" in header
    assert "2.5" in text
    assert "10" in text
    assert "True" in text or "true" in text.lower()


def test_early_pay_settings_export_ui_c1():
    page = (ROOT / "frontend/app/credit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 138" in page
    assert "/credit/settings/export" in page
    assert "Export early-pay settings CSV" in page
