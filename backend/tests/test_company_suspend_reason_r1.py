"""Company profile cannot self-suspend; tenant Save profile only."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers, platform_owner_headers

ROOT = Path(__file__).resolve().parents[2]


def test_company_page_save_profile_no_suspend():
    company = (ROOT / "frontend/app/(dashboard)/company/page.tsx").read_text(encoding="utf-8")
    assert "Save profile" in company
    assert 'aria-label="Save company profile"' in company
    assert "form-flash" in company
    assert "tenants/me/suspend" not in company
    assert "suspendReason" not in company
    assert 'aria-label="Suspend company"' not in company
    assert ">Suspend<" not in company
    assert "JSON.stringify({ reason })" not in company


@pytest.mark.asyncio
async def test_company_admin_cannot_self_suspend_via_me_api(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    denied = await ac.post(
        "/api/v1/tenants/me/suspend",
        headers=headers,
        json={"reason": "Seasonal closure — API hello-world"},
    )
    assert denied.status_code == 403, denied.text
    assert "cannot suspend" in denied.json()["detail"].lower()

    me = await ac.get("/api/v1/tenants/me", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["status"] != "suspended"

    extra = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"suspended": True},
    )
    assert extra.status_code == 422, extra.text


@pytest.mark.asyncio
async def test_platform_owner_can_still_suspend_other_tenant(client):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    slug = seed["t2"].slug
    ok = await ac.post(
        f"/api/v1/tenants/{slug}/suspend",
        headers=headers,
        json={"reason": "Non-payment — platform console"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["status"] == "suspended"

    act = await ac.post(f"/api/v1/tenants/{slug}/activate", headers=headers, json={})
    assert act.status_code == 200, act.text
    assert act.json()["data"]["status"] == "active"
