"""Industry-based module entitlements, /me payload, API isolation, shared modules."""

from __future__ import annotations

from app.packages import (
    canonicalize_industry,
    industry_allows_module,
    package_modules,
    resolve_enabled_modules,
)
from tests.conftest import auth_headers, set_tenant_industry


def test_canonicalize_industry_aliases():
    assert canonicalize_industry("Hospitality") == "hotel"
    assert canonicalize_industry("supermarket") == "mart"
    assert canonicalize_industry("retail") == "retail"
    assert canonicalize_industry("not-a-real-industry") is None
    assert canonicalize_industry("") is None
    assert canonicalize_industry(None) is None


def test_industry_allows_module_unknown_does_not_grant_verticals():
    assert industry_allows_module(None, "hotel") is False
    assert industry_allows_module("garbage", "hotel") is False
    assert industry_allows_module("retail", "hotel") is False
    assert industry_allows_module("hotel", "hotel") is True
    assert industry_allows_module("hotel", "inventory") is True
    assert industry_allows_module("retail", "inventory") is True
    assert industry_allows_module("fmcg", "fmcg") is True
    assert industry_allows_module("hotel", "fmcg") is False


def test_trial_package_includes_verticals_but_resolve_filters():
    assert "hotel" in package_modules("trial")
    assert "fmcg" in package_modules("trial")

    class T:
        package_code = "trial"
        enabled_modules = None
        industry = "retail"

    retail = resolve_enabled_modules(T())
    assert "hotel" not in retail
    assert "fmcg" not in retail
    T.industry = "hotel"
    hotel = resolve_enabled_modules(T())
    assert "hotel" in hotel
    assert "fmcg" not in hotel
    T.industry = "hospitality"
    assert "hotel" in resolve_enabled_modules(T())


async def test_retail_admin_me_and_hotel_api_denied(client):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    body = me.json()["data"]
    assert body["industry"] == "retail"
    assert body["industry_valid"] is True
    assert "hotel" not in body["enabled_modules"]
    assert "inventory" in body["enabled_modules"]
    assert "accounting" in body["enabled_modules"]

    denied = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert denied.status_code == 403, denied.text
    detail = denied.json().get("detail") or {}
    if isinstance(detail, dict):
        assert detail.get("code") == "INDUSTRY_MODULE_DISABLED"

    fmcg_denied = await ac.get("/api/v1/fmcg/schemes", headers=admin)
    assert fmcg_denied.status_code == 403, fmcg_denied.text


async def test_hotel_tenant_hotel_api_and_isolation(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")

    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    body = me.json()["data"]
    assert body["industry"] == "hotel"
    assert "hotel" in body["enabled_modules"]
    assert "fmcg" not in body["enabled_modules"]

    rooms = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert rooms.status_code == 200, rooms.text

    fmcg = await ac.get("/api/v1/fmcg/schemes", headers=admin)
    assert fmcg.status_code == 403, fmcg.text

    cashier_hotel = await ac.get("/api/v1/hotel/rooms", headers=cashier)
    assert cashier_hotel.status_code == 403, cashier_hotel.text

    beta_me = await ac.get("/api/v1/me", headers=beta)
    assert beta_me.json()["data"]["industry"] == "retail"
    beta_hotel = await ac.get("/api/v1/hotel/rooms", headers=beta)
    assert beta_hotel.status_code == 403, beta_hotel.text

    created = await ac.post(
        "/api/v1/hotel/rooms",
        headers=admin,
        json={"code": "101", "name": "Queen", "room_type": "standard", "rate_amount": 120},
    )
    assert created.status_code in {200, 201}, created.text
    listed = await ac.get("/api/v1/hotel/rooms", headers=admin)
    ids = {row["id"] for row in listed.json()["data"]}
    assert created.json()["data"]["id"] in ids

    dashboard = await ac.get("/api/v1/dashboard", headers=admin)
    assert dashboard.status_code == 200, dashboard.text


async def test_invalid_industry_does_not_grant_verticals(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "not-a-real-industry")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    body = me.json()["data"]
    assert body["industry_valid"] is False
    assert "hotel" not in (body.get("enabled_modules") or [])
    denied = await ac.get("/api/v1/hotel/rooms", headers=admin)
    assert denied.status_code == 403, denied.text


def test_hotel_sidebar_omits_unrelated_industry_features():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    nav = (root / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    shell = (root / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "HOTEL_OMIT_NAV_GROUP_IDS" in nav
    assert "'inventory'" in nav and "'sales'" in nav and "'purchases'" in nav
    assert "'stores'" in nav
    assert "'finance'" in nav and "'people'" in nav
    assert "Hostel" not in nav and "hostel" not in nav.lower()
    assert "Pharmacy" not in nav
    assert "['POS'" not in nav and '["POS"' not in nav
    assert "Restaurant and POS" in nav
    assert "['Hotel Dashboard', '/hotel', 'hotel']" in nav or '["Hotel Dashboard", "/hotel", "hotel"]' in nav
    assert "Events and Banquets" in nav
    assert "id: 'hotel'" in nav or 'id: "hotel"' in nav
    assert "from '../lib/tenantNav'" in shell
    assert "groupedTenantNav(TENANT_NAV_GROUPS, visible, industry)" in shell
    assert "HOTEL_NAV_ITEMS" in shell

