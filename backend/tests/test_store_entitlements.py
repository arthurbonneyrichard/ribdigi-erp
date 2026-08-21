"""Subscription-based multi-store entitlement enforcement tests."""

from __future__ import annotations

import asyncio

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app import store_entitlements as store_ent_svc
from tests.conftest import auth_headers


async def _admin_headers(ac, seed, *, workspace="company") -> dict:
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    if workspace == "tenant":
        headers["X-Workspace-Kind"] = "tenant"
    else:
        headers["X-Workspace-Kind"] = "company"
        headers["X-Company-ID"] = seed["c1"].id
    return headers


@pytest.mark.asyncio
async def test_store_create_below_company_limit(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 5
    seed["c1"].store_limit = 2
    await db_session.commit()

    headers = await _admin_headers(ac, seed)
    r = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "Alpha Store One", "code": "AS1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["code"] == "AS1"


@pytest.mark.asyncio
async def test_store_create_blocked_at_company_limit(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 10
    seed["c1"].store_limit = 1
    await db_session.commit()

    headers = await _admin_headers(ac, seed)
    first = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "Only Store", "code": "ONLY1"},
    )
    assert first.status_code == 200, first.text

    second = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "Overflow Store", "code": "ONLY2"},
    )
    assert second.status_code == 403, second.text
    detail = second.json()["detail"]
    assert detail["code"] == "STORE_LIMIT_REACHED"
    assert detail["scope"] == "company"
    assert detail["current_stores"] == 1
    assert detail["max_stores"] == 1


@pytest.mark.asyncio
async def test_store_create_blocked_at_tenant_entitlement(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 1
    seed["t1"].max_stores_override = None
    seed["c1"].store_limit = 5
    await db_session.commit()

    headers = await _admin_headers(ac, seed)
    first = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "Tenant Cap Store", "code": "TC1"},
    )
    assert first.status_code == 200, first.text

    second = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "Tenant Cap Overflow", "code": "TC2"},
    )
    assert second.status_code == 403, second.text
    assert second.json()["detail"]["code"] == "STORE_LIMIT_REACHED"
    assert second.json()["detail"]["scope"] == "tenant"


@pytest.mark.asyncio
async def test_unauthorized_cashier_cannot_create_store(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    headers["X-Workspace-Kind"] = "company"
    headers["X-Company-ID"] = seed["c1"].id
    r = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "No Permission", "code": "NP1"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_tenant_a_cannot_see_tenant_b_stores(client, db_session):
    from app.stores import create_store

    ac, seed = client
    await create_store(
        db_session,
        tenant_id=seed["t2"].id,
        name="Beta Store",
        code="BS1",
        company_id=seed["c2"].id,
    )
    await db_session.commit()

    headers = await _admin_headers(ac, seed)
    r = await ac.get("/api/v1/stores", headers=headers)
    assert r.status_code == 200, r.text
    codes = {row["code"] for row in r.json()["data"]}
    assert "BS1" not in codes



@pytest.mark.asyncio
async def test_tenant_admin_can_allocate_store_limit(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 5
    seed["c1"].store_limit = 1
    await db_session.commit()

    headers = await _admin_headers(ac, seed, workspace="tenant")
    r = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}/store-limit",
        headers=headers,
        json={"store_limit": 3},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["store_limit"] == 3
    assert r.json()["data"]["store_limit_explicit"] == 3


@pytest.mark.asyncio
async def test_company_admin_cannot_change_tenant_store_override(client, db_session):
    """Company workspace cannot call tenant allocation endpoint."""
    ac, seed = client
    headers = await _admin_headers(ac, seed, workspace="company")
    r = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}/store-limit",
        headers=headers,
        json={"store_limit": 9},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "TENANT_WORKSPACE_REQUIRED"


@pytest.mark.asyncio
async def test_platform_override_increases_effective_limit(client, db_session, db_engine):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app import totp as totp_svc
    from app.platform import ensure_platform_tenant
    from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID, PLATFORM_TENANT_SLUG
    from app.rbac import permissions_for_role
    from app.security import hash_password

    ac, seed = client
    seed["t1"].max_stores = 2
    seed["t1"].max_stores_override = None
    seed["c1"].store_limit = 10
    await db_session.commit()

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        db.add(
            m.User(
                tenant_id=PLATFORM_TENANT_ID,
                email="ops-stores@ribdigi.example.com",
                full_name="Platform Ops Stores",
                password_hash=hash_password("SecurePass123!"),
                role=PLATFORM_SUPER_ADMIN,
                email_verified=True,
                permissions=permissions_for_role(PLATFORM_SUPER_ADMIN),
                totp_enabled=True,
                totp_secret_enc=totp_svc.encrypt_secret(secret),
                totp_confirmed_at=__import__("datetime").datetime.utcnow(),
            )
        )
        await db.commit()

    code = pyotp.TOTP(secret).now()
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "ops-stores@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": PLATFORM_TENANT_SLUG,
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    headers = {
        "Authorization": f"Bearer {login.json()['data']['access_token']}",
        "X-Tenant-ID": PLATFORM_TENANT_ID,
    }

    r = await ac.patch(
        f"/api/v1/platform/tenants/{seed['t1'].id}/store-entitlement",
        headers=headers,
        json={"max_stores_override": 4},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["store_entitlement"]["effective"] == 4

    await db_session.refresh(seed["t1"])
    assert store_ent_svc.effective_tenant_store_limit(seed["t1"]) == 4


@pytest.mark.asyncio
async def test_plan_upgrade_syncs_max_stores_when_no_override(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 2
    seed["t1"].max_stores_override = None
    seed["t1"].plan_code = "starter"
    await db_session.commit()

    info = store_ent_svc.apply_plan_store_defaults(seed["t1"], "growth")
    assert info["synced"] is True
    assert seed["t1"].max_stores == 10  # PLAN_CATALOG growth soft_limits.stores


@pytest.mark.asyncio
async def test_downgrade_does_not_delete_stores(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 5
    seed["c1"].store_limit = 5
    await db_session.commit()

    headers = await _admin_headers(ac, seed)
    for i in range(3):
        r = await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={"name": f"Keep {i}", "code": f"KEEP{i}"},
        )
        assert r.status_code == 200, r.text

    # Downgrade entitlement below usage
    seed["t1"].max_stores = 1
    seed["t1"].max_stores_override = None
    await db_session.commit()

    count = await store_ent_svc.count_active_stores(
        db_session, tenant_id=seed["t1"].id, company_id=seed["c1"].id
    )
    assert count == 3

    blocked = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "After Downgrade", "code": "AFTER"},
    )
    assert blocked.status_code == 403
    ent = await store_ent_svc.get_tenant_store_entitlement(db_session, seed["t1"])
    assert ent["over_entitlement"] is True


@pytest.mark.asyncio
async def test_concurrent_store_creates_respect_limit(client, db_session):
    """Two near-simultaneous creates against limit=1 must yield exactly one success.

    SQLite may not fully serialize FOR UPDATE; we still assert final active count <= 1.
    """
    ac, seed = client
    seed["t1"].max_stores = 5
    seed["c1"].store_limit = 1
    await db_session.commit()

    headers = await _admin_headers(ac, seed)

    async def _create(code: str):
        return await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={"name": f"Race {code}", "code": code},
        )

    results = await asyncio.gather(_create("RACE1"), _create("RACE2"), return_exceptions=True)
    statuses = []
    for r in results:
        if isinstance(r, Exception):
            statuses.append("exc")
        else:
            statuses.append(r.status_code)

    successes = sum(1 for s in statuses if s == 200)
    assert successes <= 1
    final = await store_ent_svc.count_active_stores(
        db_session, tenant_id=seed["t1"].id, company_id=seed["c1"].id
    )
    assert final <= 1


@pytest.mark.asyncio
async def test_allocation_cannot_exceed_tenant_unallocated(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 3
    seed["c1"].store_limit = 2
    # Second company under alpha
    c_b = m.Company(
        tenant_id=seed["t1"].id,
        code="TWO",
        name="Alpha Two",
        industry="retail",
        is_active=True,
        is_default=False,
        store_limit=0,
    )
    db_session.add(c_b)
    await db_session.commit()

    headers = await _admin_headers(ac, seed, workspace="tenant")
    r = await ac.patch(
        f"/api/v1/companies/{c_b.id}/store-limit",
        headers=headers,
        json={"store_limit": 5},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "STORE_ALLOCATION_EXCEEDS_TENANT"


@pytest.mark.asyncio
async def test_allocation_cannot_go_below_active_usage(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 5
    seed["c1"].store_limit = 5
    await db_session.commit()

    headers = await _admin_headers(ac, seed)
    created = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "Keep Active", "code": "KEEP-A"},
    )
    assert created.status_code == 200, created.text

    tenant_headers = await _admin_headers(ac, seed, workspace="tenant")
    r = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}/store-limit",
        headers=tenant_headers,
        json={"store_limit": 0},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "STORE_ALLOCATION_BELOW_USAGE"


@pytest.mark.asyncio
async def test_unlimited_company_allocation_denied_when_tenant_finite(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 5
    seed["t1"].max_stores_override = None
    seed["c1"].store_limit = 2
    await db_session.commit()

    headers = await _admin_headers(ac, seed, workspace="tenant")
    r = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}/store-limit",
        headers=headers,
        json={"store_limit": -1},
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "STORE_ALLOCATION_UNLIMITED_DENIED"


@pytest.mark.asyncio
async def test_reactivate_store_blocked_when_at_limit(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 5
    seed["c1"].store_limit = 1
    await db_session.commit()

    headers = await _admin_headers(ac, seed)
    first = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "Parked Store", "code": "PARK1"},
    )
    assert first.status_code == 200, first.text
    store_id = first.json()["data"]["id"]

    parked = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert parked.status_code == 200, parked.text

    replacement = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": "Replacement Store", "code": "REPL1"},
    )
    assert replacement.status_code == 200, replacement.text

    blocked = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={"is_active": True},
    )
    assert blocked.status_code == 403, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "STORE_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_tenant_dashboard_and_entitlement_surface_over_flags(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 2
    seed["t1"].max_stores_override = None
    seed["c1"].store_limit = 5
    await db_session.commit()

    headers = await _admin_headers(ac, seed, workspace="tenant")
    dash = await ac.get("/api/v1/tenant/dashboard", headers=headers)
    assert dash.status_code == 200, dash.text
    store_ent = dash.json()["data"]["subscription"]["store_entitlement"]
    assert store_ent["over_allocated"] is True
    assert store_ent["over_entitlement"] is False
    assert store_ent["allocated_to_companies"] == 5

    snap = await ac.get("/api/v1/tenant/store-entitlement", headers=headers)
    assert snap.status_code == 200, snap.text
    payload = snap.json()["data"]
    assert "entitlement" in payload
    assert "companies" in payload
    assert payload["entitlement"]["over_allocated"] is True
    assert payload["entitlement"]["used"] == 0

    seed["t1"].max_stores = 5
    seed["c1"].store_limit = 2
    await db_session.commit()
    headers_co = await _admin_headers(ac, seed)
    for i in range(2):
        r = await ac.post(
            "/api/v1/stores",
            headers=headers_co,
            json={"name": f"Over {i}", "code": f"OVR{i}"},
        )
        assert r.status_code == 200, r.text

    seed["t1"].max_stores = 1
    seed["t1"].max_stores_override = None
    await db_session.commit()

    dash2 = await ac.get("/api/v1/tenant/dashboard", headers=headers)
    assert dash2.status_code == 200, dash2.text
    ent2 = dash2.json()["data"]["subscription"]["store_entitlement"]
    assert ent2["used"] == 2
    assert ent2["over_entitlement"] is True
    assert ent2["over_allocated"] is True


@pytest.mark.asyncio
async def test_company_create_default_allocation_clamped_when_full(client, db_session):
    ac, seed = client
    seed["t1"].max_stores = 2
    seed["t1"].max_stores_override = None
    seed["c1"].store_limit = 2
    await db_session.commit()

    headers = await _admin_headers(ac, seed, workspace="tenant")
    created = await ac.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "No Slots Co", "code": "NOSLOT"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["store_limit"] == 0

    exceeded = await ac.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Too Many", "code": "TOOMANY", "store_limit": 1},
    )
    assert exceeded.status_code == 400, exceeded.text
    assert exceeded.json()["detail"]["code"] == "STORE_ALLOCATION_EXCEEDS_TENANT"


@pytest.mark.asyncio
async def test_default_company_store_limit_uses_effective_override():
    from app.workspace import _default_company_store_limit

    tenant = m.Tenant(slug="lim", company_name="Lim", max_stores=0, max_stores_override=3)
    assert _default_company_store_limit(tenant) == 3
    tenant.max_stores_override = None
    tenant.max_stores = 0
    assert _default_company_store_limit(tenant) == 0


@pytest.mark.asyncio
async def test_platform_override_below_usage_returns_over_entitlement(client, db_session, db_engine):
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app import totp as totp_svc
    from app.platform import ensure_platform_tenant
    from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID, PLATFORM_TENANT_SLUG
    from app.rbac import permissions_for_role
    from app.security import hash_password

    ac, seed = client
    seed["t1"].max_stores = 5
    seed["t1"].max_stores_override = None
    seed["c1"].store_limit = 5
    await db_session.commit()

    headers = await _admin_headers(ac, seed)
    for i in range(2):
        r = await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={"name": f"Live {i}", "code": f"LIVE{i}"},
        )
        assert r.status_code == 200, r.text

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        db.add(
            m.User(
                tenant_id=PLATFORM_TENANT_ID,
                email="ops-over@ribdigi.example.com",
                full_name="Platform Ops Over",
                password_hash=hash_password("SecurePass123!"),
                role=PLATFORM_SUPER_ADMIN,
                email_verified=True,
                permissions=permissions_for_role(PLATFORM_SUPER_ADMIN),
                totp_enabled=True,
                totp_secret_enc=totp_svc.encrypt_secret(secret),
                totp_confirmed_at=datetime.utcnow(),
            )
        )
        await db.commit()

    code = pyotp.TOTP(secret).now()
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "ops-over@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": PLATFORM_TENANT_SLUG,
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    plat = {
        "Authorization": f"Bearer {login.json()['data']['access_token']}",
        "X-Tenant-ID": PLATFORM_TENANT_ID,
    }

    r = await ac.patch(
        f"/api/v1/platform/tenants/{seed['t1'].id}/store-entitlement",
        headers=plat,
        json={"max_stores_override": 1},
    )
    assert r.status_code == 200, r.text
    ent = r.json()["data"]["store_entitlement"]
    assert ent["effective"] == 1
    assert ent["used"] == 2
    assert ent["over_entitlement"] is True
    assert r.json()["data"]["over_entitlement"] is True

    detail = await ac.get(
        f"/api/v1/platform/tenants/{seed['t1'].id}",
        headers=plat,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["over_entitlement"] is True
    assert detail.json()["data"]["store_entitlement"]["used"] == 2
