"""Company self-suspend reason honesty — no hardcoded Admin requested."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_company_suspend_reason_ui_wired():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "suspendReason" in company
    assert "Enter a suspend reason before suspending this company" in company
    assert "JSON.stringify({ reason })" in company
    assert "Admin requested" not in company
    assert "Suspend reason (required)" in company
    assert "Required before Suspend" in company
    assert "suspended_reason" in company
    assert 'aria-label="Tenant suspend reason"' in company
    assert 'aria-label="Suspend company"' in company


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_company_me_suspend_requires_and_persists_reason(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    missing = await ac.post("/api/v1/tenants/me/suspend", headers=headers, json={})
    assert missing.status_code == 422, missing.text
    assert "reason" in missing.text.lower()

    blank = await ac.post(
        "/api/v1/tenants/me/suspend",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/tenants/me/suspend",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        "/api/v1/tenants/me/suspend",
        headers=headers,
        json={"reason": "Seasonal closure — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "suspended"
    assert body["suspended_reason"] == "Seasonal closure — API hello-world"

    # API response is source of truth (test db_session identity map may lag the override session).
    # Leave tenant suspended — fixture DB is per-test.