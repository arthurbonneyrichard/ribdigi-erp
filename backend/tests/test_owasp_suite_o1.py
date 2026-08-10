"""Stage 5 O1: OWASP automated suite beyond smoke (A01–A03, A05, A07).

Vendor ZAP / external pen test remain deferred per STAGE_5_PLAN.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from fastapi import HTTPException

from app.config import settings
from app.roles import assert_assignable_role
from tests.conftest import auth_headers

pytestmark = pytest.mark.security


@pytest.mark.asyncio
async def test_a01_cashier_cannot_create_users(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "escalated@alpha.example.com",
            "full_name": "Escalated",
            "password": "SecurePass123!",
            "role": "company_admin",
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_a01_privilege_escalation_super_admin_blocked(client, db_session):
    """company_admin cannot assign super_admin (A01 privilege escalation)."""
    ac, seed = client
    with pytest.raises(HTTPException) as exc:
        await assert_assignable_role(
            db_session,
            seed["t1"].id,
            "super_admin",
            actor_role="company_admin",
        )
    assert exc.value.status_code == 403
    assert "super_admin" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_a01_foreign_invoice_idor_404(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get(f"/api/v1/sales/invoices/{seed['inv2'].id}", headers=headers)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_a01_mismatched_tenant_header_denied(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    bad = {**headers, "X-Tenant-ID": seed["t2"].id}
    r = await ac.get("/api/v1/products", headers=bad)
    assert r.status_code == 403
    assert "cross-tenant" in r.text.lower() or "denied" in r.text.lower()


@pytest.mark.asyncio
async def test_a02_smtp_settings_never_leak_password(client):
    ac, seed = client
    # company_admin may require MFA — use super with TOTP
    import pyotp

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    r = await ac.get("/api/v1/settings/email", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "password" not in data or data.get("password") in (None, "")
    assert "smtp_password" not in data
    assert "smtp_password_enc" not in r.text.lower()
    assert "has_password" in data


@pytest.mark.asyncio
async def test_a02_tampered_jwt_rejected(client):
    ac, seed = client
    # Sign with wrong secret
    now = datetime.now(timezone.utc)
    bad = jwt.encode(
        {
            "sub": seed["mgr1"].id,
            "tenant_id": seed["t1"].id,
            "role": "super_admin",
            "type": "access",
            "jti": "tampered",
            "iat": int(now.timestamp()),
            "exp": now + timedelta(hours=1),
        },
        "wrong-secret-key-not-the-real-one!!",
        algorithm=settings.JWT_ALGORITHM,
    )
    r = await ac.get(
        "/api/v1/products",
        headers={"Authorization": f"Bearer {bad}", "X-Tenant-ID": seed["t1"].id},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_a03_sql_injection_product_search_safe(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    payload = "'; DROP TABLE products;--"
    r = await ac.get(
        "/api/v1/inventory/products/lookup",
        headers=headers,
        params={"q": payload},
    )
    assert r.status_code == 200, r.text
    # Still can list products afterward (injection did not break schema)
    again = await ac.get("/api/v1/products", headers=headers)
    assert again.status_code == 200
    assert isinstance(again.json()["data"], list)


@pytest.mark.asyncio
async def test_a03_xss_payload_stored_as_json_text(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    xss = "<script>alert(1)</script>"
    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": xss,
            "sku": "XSS-O1",
            "cost_price": 1,
            "selling_price": 2,
            "stock_qty": 0,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["name"] == xss
    # JSON response must not include executable HTML context — Content-Type is JSON
    assert "application/json" in created.headers.get("content-type", "")
    assert "<html" not in created.text.lower()


@pytest.mark.asyncio
async def test_a05_error_404_has_no_traceback(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000099",
        headers=headers,
    )
    assert r.status_code == 404
    blob = r.text.lower()
    assert "traceback" not in blob
    assert "file \"" not in blob
    assert "password_hash" not in blob


@pytest.mark.asyncio
async def test_a07_missing_and_garbage_bearer_rejected(client):
    ac, _seed = client
    missing = await ac.get("/api/v1/products")
    assert missing.status_code == 401
    garbage = await ac.get(
        "/api/v1/products",
        headers={"Authorization": "Bearer not-a-jwt", "X-Tenant-ID": "alpha"},
    )
    assert garbage.status_code == 401


@pytest.mark.asyncio
async def test_a07_expired_access_token_rejected(client, db_session):
    ac, seed = client
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": seed["mgr1"].id,
            "tenant_id": seed["t1"].id,
            "role": "store_manager",
            "type": "access",
            "jti": "expired-o1",
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": now - timedelta(hours=1),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    r = await ac.get(
        "/api/v1/products",
        headers={
            "Authorization": f"Bearer {expired}",
            "X-Tenant-ID": seed["t1"].id,
        },
    )
    assert r.status_code == 401
