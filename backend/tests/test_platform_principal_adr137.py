"""ADR-137 platform principal isolation tests."""

from __future__ import annotations

import pyotp
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import models as m
from app import totp as totp_svc
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID, PLATFORM_TENANT_SLUG
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers


async def _seed_platform_admin(db: AsyncSession) -> tuple[m.User, str]:
    await ensure_platform_tenant(db)
    secret = pyotp.random_base32()
    user = m.User(
        tenant_id=PLATFORM_TENANT_ID,
        email="ops@ribdigi.example.com",
        full_name="Platform Ops",
        password_hash=hash_password("SecurePass123!"),
        role=PLATFORM_SUPER_ADMIN,
        email_verified=True,
        permissions=permissions_for_role(PLATFORM_SUPER_ADMIN),
        totp_enabled=True,
        totp_secret_enc=totp_svc.encrypt_secret(secret),
        totp_confirmed_at=__import__("datetime").datetime.utcnow(),
    )
    db.add(user)
    await db.commit()
    return user, secret


@pytest.mark.asyncio
async def test_tenant_roles_cannot_access_platform_apis(client):
    ac, seeded = client
    # Cashier does not require 2FA enrollment — assert principal gate specifically.
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    for path in (
        "/api/v1/platform/dashboard",
        "/api/v1/platform/tenants",
        "/api/v1/platform/health",
        "/api/v1/platform/audit",
    ):
        r = await ac.get(path, headers=cash)
        assert r.status_code == 403, path
        detail = r.json().get("detail")
        code = detail.get("code") if isinstance(detail, dict) else None
        assert code == "PLATFORM_PRINCIPAL_REQUIRED"

    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/platform/dashboard", headers=mgr)
    assert r.status_code == 403
    detail = r.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "PLATFORM_PRINCIPAL_REQUIRED"

    # company_admin may hit 2FA enrollment gate first; still must not succeed.
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/platform/dashboard", headers=admin)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_platform_login_redirect_and_isolation(client, db_engine):
    ac, seeded = client
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        _user, secret = await _seed_platform_admin(db)

    code = pyotp.TOTP(secret).now()
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "ops@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": PLATFORM_TENANT_SLUG,
            "totp_code": code,
        },
    )
    assert login.status_code == 200, login.text
    data = login.json()["data"]
    assert data["principal"] == "platform"
    assert data["redirect_path"] == "/platform/dashboard"
    assert data["user"]["principal"] == "platform"
    assert data["user"]["tenant_id"] == PLATFORM_TENANT_ID

    headers = {
        "Authorization": f"Bearer {data['access_token']}",
        "X-Tenant-ID": PLATFORM_TENANT_ID,
    }
    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["principal"] == "platform"
    assert me.json()["data"]["redirect_path"] == "/platform/dashboard"

    dash = await ac.get("/api/v1/platform/dashboard", headers=headers)
    assert dash.status_code == 200, dash.text
    body = dash.json()["data"]
    assert body["billing"]["deferred"] is True
    assert body["billing"]["mrr"] is None
    # seeded customer tenants alpha+beta
    assert body["total_tenants"] >= 2
    assert PLATFORM_TENANT_ID not in str(body)

    tenants = await ac.get("/api/v1/platform/tenants", headers=headers)
    assert tenants.status_code == 200
    items = tenants.json()["data"]["items"]
    ids = {t["id"] for t in items}
    assert PLATFORM_TENANT_ID not in ids
    assert seeded["t1"].id in ids

    # Platform cannot use tenant ERP business modules
    erp = await ac.get("/api/v1/dashboard", headers=headers)
    assert erp.status_code == 403
    detail = erp.json().get("detail")
    assert isinstance(detail, dict)
    assert detail.get("code") == "PLATFORM_USE_PLATFORM_API"

    products = await ac.get("/api/v1/products", headers=headers)
    assert products.status_code == 403


@pytest.mark.asyncio
async def test_platform_suspend_activate_customer_tenant(client, db_engine):
    ac, seeded = client
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        _user, secret = await _seed_platform_admin(db)

    code = pyotp.TOTP(secret).now()
    login = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "ops@ribdigi.example.com",
            "password": "SecurePass123!",
            "tenant_id": PLATFORM_TENANT_SLUG,
            "totp_code": code,
        },
    )
    headers = {
        "Authorization": f"Bearer {login.json()['data']['access_token']}",
        "X-Tenant-ID": PLATFORM_TENANT_ID,
    }
    tid = seeded["t2"].id
    sus = await ac.post(f"/api/v1/platform/tenants/{tid}/suspend", headers=headers)
    assert sus.status_code == 200, sus.text
    assert sus.json()["data"]["status"] == "suspended"

    # Cannot suspend platform tenant
    bad = await ac.post(f"/api/v1/platform/tenants/{PLATFORM_TENANT_ID}/suspend", headers=headers)
    assert bad.status_code == 400

    act = await ac.post(f"/api/v1/platform/tenants/{tid}/activate", headers=headers)
    assert act.status_code == 200
    assert act.json()["data"]["status"] == "active"


@pytest.mark.asyncio
async def test_reserved_slug_rejected_on_register(client):
    ac, _seeded = client
    r = await ac.post(
        "/api/v1/tenants",
        json={
            "slug": PLATFORM_TENANT_SLUG,
            "company_name": "Evil Co",
            "industry": "retail",
            "currency": "USD",
            "admin_email": "evil@example.com",
            "admin_password": "SecurePass123!",
            "admin_full_name": "Evil Admin",
        },
    )
    assert r.status_code == 400
    assert "reserved" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_tenant_login_still_redirects_to_dashboard(client):
    ac, _seeded = client
    headers_body = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    # Re-login to inspect payload
    r = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "admin@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["principal"] == "tenant"
    assert data["redirect_path"] == "/dashboard"
    assert headers_body["Authorization"].startswith("Bearer ")
