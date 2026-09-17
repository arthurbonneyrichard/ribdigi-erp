"""Platform tenant Suspend reason honesty — FE sends real reason (no window.prompt)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_platform_suspend_reason_ui_wired():
    plat = (ROOT / "frontend/app/platform/page.tsx").read_text(encoding="utf-8")
    assert "suspendReason" in plat
    assert "Enter a suspend reason before suspending a tenant" in plat
    assert "JSON.stringify({ reason })" in plat
    assert "Suspended_reason" not in plat  # typo guard
    assert "suspended_reason" in plat
    assert "Required before Suspend" in plat
    assert 'aria-label="Tenant suspend reason"' in plat
    assert "aria-label={`Suspend tenant ${t.id}`}" in plat
    # Suspend path must not use window.prompt
    assert "window.prompt" not in plat
    assert "window.confirm(`Suspend ${row.company_name}?`)" in plat


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_platform_suspend_requires_and_persists_reason(client):
    ac, seed = client
    headers = await _super(ac, seed)
    slug = seed["t2"].slug

    missing = await ac.post(f"/api/v1/tenants/{slug}/suspend", headers=headers, json={})
    assert missing.status_code == 422, missing.text
    assert "reason" in missing.text.lower()

    blank = await ac.post(
        f"/api/v1/tenants/{slug}/suspend",
        headers=headers,
        json={"reason": "   "},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/tenants/{slug}/suspend",
        headers=headers,
        json={"reason": "!!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/tenants/{slug}/suspend",
        headers=headers,
        json={"reason": "Non-payment — API hello-world"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "suspended"
    assert body["suspended_reason"] == "Non-payment — API hello-world"

    act = await ac.post(f"/api/v1/tenants/{slug}/activate", headers=headers, json={})
    assert act.status_code == 200, act.text
    assert act.json()["data"]["status"] == "active"
    assert act.json()["data"].get("suspended_reason") in (None, "")
