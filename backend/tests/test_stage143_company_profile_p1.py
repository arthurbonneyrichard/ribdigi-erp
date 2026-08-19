"""Stage 143 P1 — company profile CSV export."""

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
async def test_company_profile_export_csv(client):
    ac, seed = client
    headers = await _super(ac, seed)

    exported = await ac.get("/api/v1/tenants/me/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "company_name" in header and "slug" in header and "plan_code" in header
    assert "billing_deferred" in header
    assert seed["t1"].slug in text or "alpha" in text.lower()
    assert "password" not in header.lower()
    assert "secret" not in header.lower()
    assert "smtp_password" not in text.lower()


def test_company_profile_export_ui_p1():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 143" in page
    assert "/tenants/me/export" in page
    assert "Export profile CSV" in page
    assert 'id="profile"' in page
