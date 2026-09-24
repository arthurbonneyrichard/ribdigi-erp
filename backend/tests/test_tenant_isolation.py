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
async def test_super_admin_can_activate_suspended_tenant(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    r = await ac.post(
        f"/api/v1/tenants/{seed['t2'].slug}/suspend",
        headers=headers,
        json={"reason": "test"},
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

    code2 = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers2 = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code2
    )
    activated = await ac.post(
        f"/api/v1/tenants/{seed['t2'].id}/activate",
        headers=headers2,
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
