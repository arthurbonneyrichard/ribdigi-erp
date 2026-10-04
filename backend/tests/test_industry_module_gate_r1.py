"""Business-type (industry) module gating — Hotel vs FMCG vs core.

Package entitlements alone must not expose industry-specific modules to
unrelated business types. Backend authorization is the security boundary;
frontend menus consume the same filtered enabled_modules list.
"""

from __future__ import annotations

from uuid import uuid4

import pyotp
import pytest

from app import models as m
from app import packages as packages_svc
from tests.conftest import auth_headers


def test_industry_module_allowlist_unit():
    assert packages_svc.industry_allows_module("hotel", "hotel")
    assert not packages_svc.industry_allows_module("hotel", "fmcg")
    assert packages_svc.industry_allows_module("fmcg", "fmcg")
    assert not packages_svc.industry_allows_module("fmcg", "hotel")
    assert not packages_svc.industry_allows_module("retail", "hotel")
    assert not packages_svc.industry_allows_module("pharmacy", "fmcg")
    # Shared core always allowed from industry perspective
    assert packages_svc.industry_allows_module("retail", "inventory")
    assert packages_svc.industry_allows_module("hotel", "pos")


def test_resolve_enabled_modules_filters_by_industry():
    class T:
        package_code = "professional"
        enabled_modules = None
        industry = "retail"

    retail = packages_svc.resolve_enabled_modules(T())
    assert "hotel" not in retail
    assert "fmcg" not in retail
    assert "pos" in retail

    T.industry = "hotel"
    hotel = packages_svc.resolve_enabled_modules(T())
    assert "hotel" in hotel
    assert "fmcg" not in hotel

    T.industry = "fmcg"
    fmcg = packages_svc.resolve_enabled_modules(T())
    assert "fmcg" in fmcg
    assert "hotel" not in fmcg


async def _set_industry(db_session, tenant: m.Tenant, industry: str):
    tenant.industry = industry
    await db_session.commit()
    await db_session.refresh(tenant)


@pytest.mark.asyncio
async def test_retail_tenant_denied_hotel_and_fmcg_apis(client, seeded, db_session):
    ac, seed = client
    await _set_industry(db_session, seed["t1"], "retail")
    # Use tenant company_admin — platform roles intentionally bypass package/industry gates.
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200
    mods = me.json()["data"]["enabled_modules"]
    assert me.json()["data"]["industry"] == "retail"
    assert "hotel" not in mods
    assert "fmcg" not in mods

    hotel = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert hotel.status_code == 403
    assert hotel.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"

    fmcg = await ac.get("/api/v1/fmcg/schemes", headers=admin)
    assert fmcg.status_code == 403
    assert fmcg.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"


@pytest.mark.asyncio
async def test_hotel_tenant_denied_fmcg_and_allowed_hotel(client, seeded, db_session):
    ac, seed = client
    await _set_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=admin)
    mods = me.json()["data"]["enabled_modules"]
    assert "hotel" in mods
    assert "fmcg" not in mods

    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert rooms.status_code == 200, rooms.text

    fmcg = await ac.post(
        "/api/v1/fmcg/schemes",
        headers=admin,
        json={"code": f"X{uuid4().hex[:4]}", "name": "Nope", "scheme_type": "percent", "value": 1},
    )
    assert fmcg.status_code == 403
    assert fmcg.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"


@pytest.mark.asyncio
async def test_fmcg_tenant_denied_hotel_and_allowed_fmcg(client, seeded, db_session):
    ac, seed = client
    await _set_industry(db_session, seed["t1"], "fmcg")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=admin)
    mods = me.json()["data"]["enabled_modules"]
    assert "fmcg" in mods
    assert "hotel" not in mods

    schemes = await ac.get("/api/v1/fmcg/schemes", headers=admin)
    assert schemes.status_code == 200, schemes.text

    hotel = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": f"H{uuid4().hex[:4]}", "name": "Nope", "rate_amount": 10},
    )
    assert hotel.status_code == 403
    assert hotel.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"


@pytest.mark.asyncio
async def test_cannot_assign_hotel_module_to_retail_via_platform(client, seeded, db_session):
    ac, seed = client
    await _set_industry(db_session, seed["t1"], "retail")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    r = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/modules",
        headers=admin,
        json={"enabled_modules": ["dashboard", "inventory", "hotel", "notifications", "security"]},
    )
    assert r.status_code == 422, r.text
    assert "hotel" in r.text.lower() or "business type" in r.text.lower()
