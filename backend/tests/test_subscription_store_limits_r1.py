"""Subscription-based store limits (Company == Tenant)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import packages as packages_svc
from app import store_entitlements as store_ent_svc
from app import tenants as tenants_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_package_catalog_exposes_max_stores():
    assert packages_svc.package_modules  # smoke
    assert store_ent_svc.package_max_stores("trial") == 1
    assert store_ent_svc.package_max_stores("starter") == 1
    assert store_ent_svc.package_max_stores("professional") == 10
    assert store_ent_svc.package_max_stores("enterprise") is None
    pkgs = packages_svc.list_packages()
    pro = next(p for p in pkgs if p["code"] == "professional")
    assert pro["max_stores"] == 10
    ent = next(p for p in pkgs if p["code"] == "enterprise")
    assert ent["max_stores"] is None


def test_effective_limit_override_and_allocation():
    tenant = m.Tenant(
        slug="x",
        company_name="X",
        package_code="professional",
        max_stores_override=None,
        store_limit=None,
    )
    assert store_ent_svc.subscription_store_entitlement(tenant) == 10
    assert store_ent_svc.effective_store_limit(tenant) == 10

    tenant.max_stores_override = 3
    assert store_ent_svc.subscription_store_entitlement(tenant) == 3
    assert store_ent_svc.effective_store_limit(tenant) == 3

    tenant.store_limit = 2
    assert store_ent_svc.effective_store_limit(tenant) == 2

    tenant.store_limit = 9  # above override entitlement → clamped by min()
    assert store_ent_svc.effective_store_limit(tenant) == 3

    tenant.max_stores_override = None
    tenant.package_code = "enterprise"
    tenant.store_limit = None
    assert store_ent_svc.effective_store_limit(tenant) is None


def test_stores_entitlement_ui_wired():
    stores = (ROOT / "frontend/app/(dashboard)/stores/page.tsx").read_text(encoding="utf-8")
    assert "/stores/entitlement" in stores
    assert "Stores Used" in stores
    assert "store-limit" in stores
    assert "canCreateStore" in stores
    platform = (ROOT / "frontend/app/(dashboard)/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "max_stores_override" in platform
    assert "store-entitlement" in platform
    assert "Single store" in platform
    assert "Multi-store" in platform
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "tenantIsMultiStore" in shell
    assert "CASHIER_NAV_MODULES" in shell
    nav = (ROOT / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    assert "filterNavForStoreMode" in nav
    cashier_line = next(
        line for line in nav.splitlines() if "export const CASHIER_NAV_MODULES: string[]" in line
    )
    assert cashier_line == (
        "export const CASHIER_NAV_MODULES: string[] = ['sales', 'pos', 'support'];"
    )
    assert "'reports'" not in cashier_line
    assert "'company'" not in cashier_line


def test_is_multi_store_and_create_override():
    assert store_ent_svc.is_multi_store(
        m.Tenant(slug="a", company_name="A", package_code="professional")
    )
    assert not store_ent_svc.is_multi_store(
        m.Tenant(slug="b", company_name="B", package_code="starter")
    )
    assert not store_ent_svc.is_multi_store(
        m.Tenant(slug="c", company_name="C", package_code="professional", max_stores_override=1)
    )
    assert store_ent_svc.resolve_create_max_stores_override("single", None) == 1
    assert store_ent_svc.resolve_create_max_stores_override("multi", None) == 10
    assert store_ent_svc.resolve_create_max_stores_override("multi", 5) == 5
    flags = store_ent_svc.ui_store_flags(
        m.Tenant(slug="d", company_name="D", package_code="starter", max_stores_override=1)
    )
    assert flags["max_stores"] == 1
    assert flags["multi_store"] is False


async def _admin(ac, seed):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _cashier(ac, seed):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_create_store_below_and_at_limit(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    tenant = await tenants_svc.get_tenant(db_session, seed["t1"].id)
    await tenants_svc.set_max_stores_override(db_session, tenant, 2)
    await db_session.commit()

    r1 = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "S1", "code": "LIM-S1"},
    )
    assert r1.status_code == 200, r1.text
    r2 = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "S2", "code": "LIM-S2"},
    )
    assert r2.status_code == 200, r2.text
    blocked = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "S3", "code": "LIM-S3"},
    )
    assert blocked.status_code == 403, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "STORE_LIMIT_REACHED"
    assert detail["stores_used"] == 2
    assert detail["stores_limit"] == 2
    assert "Upgrade" in detail["message"]


@pytest.mark.asyncio
async def test_unauthorized_cashier_cannot_create_store(client):
    ac, seed = client
    cashier = await _cashier(ac, seed)
    r = await ac.post(
        "/api/v1/stores",
        headers=cashier,
        json={"name": "Nope", "code": "NOPE"},
    )
    assert r.status_code in {401, 403}, r.text


@pytest.mark.asyncio
async def test_tenant_isolation_store_get(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    created = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "Alpha Only", "code": "ISO-A"},
    )
    assert created.status_code == 200, created.text
    sid = created.json()["data"]["id"]

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    # beta cashier lacks stores write/read typically — use beta admin if any; seed has no beta admin
    # Create beta company_admin via direct... use beta cashier stores read should 403
    steal = await ac.get(f"/api/v1/stores/{sid}", headers=beta)
    assert steal.status_code in {403, 404}, steal.text


@pytest.mark.asyncio
async def test_tenant_admin_store_limit_allocation(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    tenant = await tenants_svc.get_tenant(db_session, seed["t1"].id)
    # professional entitlement 10; allocate 1
    r = await ac.patch(
        "/api/v1/tenants/me/store-limit",
        headers=admin,
        json={"store_limit": 1},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["store_limit"] == 1
    assert r.json()["data"]["subscription"]["effective_store_limit"] == 1

    ok = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "Alloc1", "code": "ALC-1"},
    )
    assert ok.status_code == 200, ok.text
    blocked = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "Alloc2", "code": "ALC-2"},
    )
    assert blocked.status_code == 403, blocked.text

    # Cannot allocate above entitlement
    bad = await ac.patch(
        "/api/v1/tenants/me/store-limit",
        headers=admin,
        json={"store_limit": 999},
    )
    assert bad.status_code == 422, bad.text


@pytest.mark.asyncio
async def test_company_admin_cannot_set_platform_override(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    r = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/store-entitlement",
        headers=admin,
        json={"max_stores_override": 50},
    )
    assert r.status_code in {401, 403}, r.text


@pytest.mark.asyncio
async def test_platform_override_and_upgrade_downgrade(client, db_session):
    ac, seed = client
    super_h = await _super(ac, seed)
    admin = await _admin(ac, seed)

    # Override to 1
    o = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/store-entitlement",
        headers=super_h,
        json={"max_stores_override": 1},
    )
    assert o.status_code == 200, o.text
    assert o.json()["data"]["max_stores_override"] == 1

    s1 = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "OV1", "code": "OV-1"},
    )
    assert s1.status_code == 200, s1.text
    blocked = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "OV2", "code": "OV-2"},
    )
    assert blocked.status_code == 403, blocked.text

    # Upgrade override to 2 → create allowed
    o2 = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/store-entitlement",
        headers=super_h,
        json={"max_stores_override": 2},
    )
    assert o2.status_code == 200, o2.text
    s2 = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "OV2", "code": "OV-2"},
    )
    assert s2.status_code == 200, s2.text
    sid2 = s2.json()["data"]["id"]

    # Downgrade override to 1 — must NOT delete stores
    o3 = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/store-entitlement",
        headers=super_h,
        json={"max_stores_override": 1},
    )
    assert o3.status_code == 200, o3.text
    listed = await ac.get("/api/v1/stores", headers=admin)
    ids = {r["id"] for r in listed.json()["data"]}
    assert s1.json()["data"]["id"] in ids
    assert sid2 in ids
    assert o3.json()["data"]["store_usage"]["over_entitlement"] is True

    # Cannot create while over/at limit
    blocked2 = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"name": "OV3", "code": "OV-3"},
    )
    assert blocked2.status_code == 403, blocked2.text

    # Deactivate one, still at 1 active if other stays active — deactivate sid2
    deact = await ac.patch(
        f"/api/v1/stores/{sid2}",
        headers=admin,
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    # Reactivate while already at limit (1 active) → blocked
    react = await ac.patch(
        f"/api/v1/stores/{sid2}",
        headers=admin,
        json={"is_active": True},
    )
    assert react.status_code == 403, react.text


@pytest.mark.asyncio
async def test_subscription_assign_sets_override(client):
    ac, seed = client
    super_h = await _super(ac, seed)
    r = await ac.post(
        f"/api/v1/tenants/{seed['t1'].slug}/subscription",
        headers=super_h,
        json={
            "package_code": "starter",
            "term_value": 1,
            "term_unit": "months",
            "max_stores_override": 4,
            "enabled_modules": [
                "dashboard",
                "company",
                "inventory",
                "sales",
                "pos",
                "accounting",
                "expenses",
                "notifications",
                "security",
                "users",
                "customers",
                "suppliers",
                "stores",
            ],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["max_stores_override"] == 4
    assert r.json()["data"]["subscription"]["effective_store_limit"] == 4


@pytest.mark.asyncio
async def test_concurrent_store_create_respects_limit(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    tenant = await tenants_svc.get_tenant(db_session, seed["t1"].id)
    await tenants_svc.set_max_stores_override(db_session, tenant, 1)
    # Clear any existing active stores from other tests? each client fixture is fresh DB
    await db_session.commit()

    async def create_one(code: str):
        return await ac.post(
            "/api/v1/stores",
            headers=admin,
            json={"name": code, "code": code},
        )

    r1, r2 = await asyncio.gather(create_one("CONC-1"), create_one("CONC-2"))
    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 403], (r1.text, r2.text)

    rows = (
        await db_session.execute(
            select(m.Store).where(m.Store.tenant_id == seed["t1"].id, m.Store.is_active.is_(True))
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_stores_entitlement_endpoint(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    r = await ac.get("/api/v1/stores/entitlement", headers=admin)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "stores_active" in data
    assert "effective_store_limit" in data
    assert data["effective_store_limit"] == 10  # professional seed
    assert data["multi_store"] is True
    assert data["max_stores"] == 10


@pytest.mark.asyncio
async def test_me_exposes_multi_store_from_tenant_columns(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    body = me.json()["data"]
    assert body["multi_store"] is True
    assert body["max_stores"] == 10

    tenant = await tenants_svc.get_tenant(db_session, seed["t1"].id)
    await tenants_svc.set_max_stores_override(db_session, tenant, 1)
    await db_session.commit()
    me2 = await ac.get("/api/v1/me", headers=admin)
    assert me2.status_code == 200, me2.text
    assert me2.json()["data"]["multi_store"] is False
    assert me2.json()["data"]["max_stores"] == 1


@pytest.mark.asyncio
async def test_create_tenant_store_mode_sets_override(client, db_session):
    ac, seed = client
    from tests.conftest import platform_owner_headers

    headers = await platform_owner_headers(ac, seed)
    single = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={
            "company_name": "Solo Mart",
            "slug": "solo-mart-store-mode",
            "industry": "retail",
            "currency": "GHS",
            "admin_email": "solo.admin@example.com",
            "admin_password": "SecurePass123!",
            "store_mode": "single",
        },
    )
    assert single.status_code == 200, single.text
    row = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "solo-mart-store-mode"))
    ).scalar_one()
    assert row.max_stores_override == 1
    assert store_ent_svc.is_multi_store(row) is False

    multi = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={
            "company_name": "Chain Mart",
            "slug": "chain-mart-store-mode",
            "industry": "retail",
            "currency": "GHS",
            "admin_email": "chain.admin@example.com",
            "admin_password": "SecurePass123!",
            "store_mode": "multi",
        },
    )
    assert multi.status_code == 200, multi.text
    row2 = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "chain-mart-store-mode"))
    ).scalar_one()
    assert row2.max_stores_override == 10
    assert store_ent_svc.is_multi_store(row2) is True
