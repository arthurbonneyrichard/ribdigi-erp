import pyotp
import pytest

from app import tenants as tenants_svc
from app import models as m
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_products_list_is_tenant_scoped(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/products", headers=headers)
    assert r.status_code == 200
    rows = r.json()["data"]
    names = {p["name"] if isinstance(p, dict) else p for p in rows}
    # jsonable_encoder may return dicts with name key
    if rows and isinstance(rows[0], dict):
        names = {p["name"] for p in rows}
    assert "Alpha Widget" in names
    assert "Beta Widget" not in names


@pytest.mark.asyncio
async def test_foreign_invoice_returns_404(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get(f"/api/v1/sales/invoices/{seed['inv2'].id}", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_mismatched_x_tenant_header_denied(client):
    ac, seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    headers["X-Tenant-ID"] = seed["t2"].id
    r = await ac.get("/api/v1/products", headers=headers)
    assert r.status_code == 403
    assert "Cross-tenant" in r.json()["detail"]


@pytest.mark.asyncio
async def test_suspended_tenant_cannot_login(client, db_session):
    ac, seed = client
    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    await tenants_svc.suspend_tenant(db_session, tenant, reason="nonpayment")
    await db_session.commit()

    r = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@alpha.example.com",
            "password": "SecurePass123!",
            "tenant_id": "alpha",
        },
    )
    assert r.status_code == 403
    assert "suspended" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_customer_super_admin_cross_tenant_lifecycle_retired(client):
    """ADR-137: legacy /tenants* cross-tenant ops return 410; use /platform/*."""
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    listed = await ac.get("/api/v1/tenants", headers=headers)
    assert listed.status_code == 410
    assert listed.json()["detail"]["code"] == "PLATFORM_API_REQUIRED"

    r = await ac.post(
        f"/api/v1/tenants/{seed['t2'].slug}/suspend",
        headers=headers,
        json={"reason": "test"},
    )
    assert r.status_code == 410
    assert r.json()["detail"]["code"] == "PLATFORM_API_REQUIRED"
    assert "/api/v1/platform/tenants/" in r.json()["detail"]["migrate_to"]

    act = await ac.post(
        f"/api/v1/tenants/{seed['t2'].id}/activate",
        headers=headers,
    )
    assert act.status_code == 410


@pytest.mark.asyncio
async def test_platform_path_suspend_activate_customer_tenant(client, db_engine):
    """Cross-tenant suspend/activate lives on /api/v1/platform/tenants/*."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app import totp as totp_svc
    from app.platform import ensure_platform_tenant
    from app.platform_const import PLATFORM_SUPER_ADMIN, PLATFORM_TENANT_ID, PLATFORM_TENANT_SLUG
    from app.rbac import permissions_for_role
    from app.security import hash_password

    ac, seed = client
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as db:
        await ensure_platform_tenant(db)
        secret = pyotp.random_base32()
        db.add(
            m.User(
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
        )
        await db.commit()

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
    headers = {
        "Authorization": f"Bearer {login.json()['data']['access_token']}",
        "X-Tenant-ID": PLATFORM_TENANT_ID,
    }

    r = await ac.post(
        f"/api/v1/platform/tenants/{seed['t2'].id}/suspend",
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "suspended"

    denied = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@beta.example.com",
            "password": "SecurePass123!",
            "tenant_id": "beta",
        },
    )
    assert denied.status_code == 403

    activated = await ac.post(
        f"/api/v1/platform/tenants/{seed['t2'].id}/activate",
        headers=headers,
    )
    assert activated.status_code == 200
    assert activated.json()["data"]["status"] == "active"

    ok = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": "cashier@beta.example.com",
            "password": "SecurePass123!",
            "tenant_id": "beta",
        },
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_ensure_tenant_owns_helper(db_session, seeded):
    with pytest.raises(Exception) as exc:
        await tenants_svc.ensure_tenant_owns(
            db_session,
            m.Product,
            tenant_id=seeded["t1"].id,
            entity_id=seeded["p2"].id,
        )
    assert exc.value.status_code == 404

    owned = await tenants_svc.ensure_tenant_owns(
        db_session,
        m.Product,
        tenant_id=seeded["t1"].id,
        entity_id=seeded["p1"].id,
    )
    assert owned.id == seeded["p1"].id
