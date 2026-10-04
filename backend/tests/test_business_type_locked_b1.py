"""Business type is locked for company users; Platform Owner can change it."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers, platform_owner_headers


@pytest.mark.asyncio
async def test_company_admin_cannot_change_industry(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    resp = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"industry": "hotel"},
    )
    assert resp.status_code == 403, resp.text
    assert "business type" in resp.text.lower() or "platform owner" in resp.text.lower()


@pytest.mark.asyncio
async def test_platform_owner_can_change_industry_with_reason(client):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    tenant_id = seed["t1"].id
    resp = await ac.patch(
        f"/api/v1/tenants/{tenant_id}/industry",
        headers=headers,
        json={"industry": "pharmacy", "reason": "Tenant contracted as a pharmacy"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["industry"] == "pharmacy"


@pytest.mark.asyncio
async def test_create_tenant_blank_industry_rejected(client):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    missing = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={
            "company_name": "No Type Co",
            "slug": "no-type-co",
            "industry": "",
            "currency": "GHS",
            "admin_email": "admin@notype.example.com",
            "admin_password": "SecurePass123!",
        },
    )
    assert missing.status_code == 422, missing.text
