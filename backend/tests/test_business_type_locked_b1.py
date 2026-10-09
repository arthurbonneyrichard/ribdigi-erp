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

    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/pharmacy/prescriptions",
        headers=admin,
        json={"items": [{"product_id": seed["p1"].id, "quantity": 1}]},
    )
    assert created.status_code == 200, created.text
    rx_id = created.json()["data"]["id"]

    locked = await ac.patch(
        f"/api/v1/tenants/{tenant_id}/industry",
        headers=headers,
        json={"industry": "retail", "reason": "Reverted to retail operations"},
    )
    assert locked.status_code == 200, locked.text
    assert locked.json()["data"]["industry"] == "retail"
    denied = await ac.get("/api/v1/pharmacy/prescriptions", headers=admin)
    assert denied.status_code == 403, denied.text
    still = await ac.get(f"/api/v1/pharmacy/prescriptions/{rx_id}", headers=admin)
    assert still.status_code == 403
    dash = await ac.get("/api/v1/dashboard", headers=admin)
    assert dash.status_code == 200
    ids = {row["id"] for row in dash.json()["data"]["industry_features"]}
    assert "prescriptions" not in ids
    assert dash.json()["data"].get("rx_queue") is None


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


@pytest.mark.asyncio
async def test_hotel_fmcg_and_restaurant_are_selectable_for_new_companies(client):
    """Restaurant, Hotel, and FMCG create successfully. Retail, Pharmacy, Wholesale, and Hospital stay selectable."""
    from app.tenants import RETIRED_PROVISION_INDUSTRIES

    assert RETIRED_PROVISION_INDUSTRIES == frozenset()
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    selectable = (
        ("hotel", "Hotel Co", "hotel-co", "admin@hotel-co.example.com"),
        ("fmcg", "FMCG Co", "fmcg-co", "admin@fmcg-co.example.com"),
        ("restaurant", "Restaurant Co", "restaurant-co", "admin@restaurant-co.example.com"),
        ("retail", "Retail Co", "retail-co", "admin@retail-co.example.com"),
        ("pharmacy", "Pharmacy Co", "pharmacy-co", "admin@pharmacy-co.example.com"),
        ("wholesale", "Wholesale Co", "wholesale-co", "admin@wholesale-co.example.com"),
        ("hospital", "Hospital Co", "hospital-co", "admin@hospital-co.example.com"),
    )
    for industry, company_name, slug, email in selectable:
        created = await ac.post(
            "/api/v1/tenants",
            headers=headers,
            json={
                "company_name": company_name,
                "slug": slug,
                "industry": industry,
                "currency": "GHS",
                "admin_email": email,
                "admin_password": "SecurePass123!",
            },
        )
        assert created.status_code == 200, created.text
        assert created.json()["data"]["slug"] == slug

    listed = await ac.get("/api/v1/tenants", headers=headers)
    assert listed.status_code == 200, listed.text
    by_slug = {row["slug"]: row["industry"] for row in listed.json()["data"]}
    for industry, _company_name, slug, _email in selectable:
        assert by_slug[slug] == industry

    changed = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].id}/industry",
        headers=headers,
        json={"industry": "fmcg", "reason": "Switching an existing company to FMCG"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["data"]["industry"] == "fmcg"
