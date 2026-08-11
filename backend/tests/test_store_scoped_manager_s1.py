"""Stage 81 S1 — Store-scoped manager dashboard + dual-console isolation matrix."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_store_manager_dashboard_includes_store_scope(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    mgr = seed["mgr1"]
    store = m.Store(
        tenant_id=tid,
        name="Alpha Main",
        code="A-MAIN",
        manager_id=mgr.id,
        is_active=True,
    )
    other = m.Store(
        tenant_id=tid,
        name="Alpha Other",
        code="A-OTHER",
        manager_id=None,
        is_active=True,
    )
    db_session.add_all([store, other])
    await db_session.flush()
    db_session.add(
        m.SalesInvoice(
            tenant_id=tid,
            invoice_number="INV-MGR-1",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=40,
            tax_amount=0,
            total_amount=40,
            store_id=store.id,
            posted_at=__import__("datetime").datetime.utcnow(),
        )
    )
    db_session.add(
        m.SalesInvoice(
            tenant_id=tid,
            invoice_number="INV-OTHER-1",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=999,
            tax_amount=0,
            total_amount=999,
            store_id=other.id,
            posted_at=__import__("datetime").datetime.utcnow(),
        )
    )
    await db_session.commit()

    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data.get("view") == "store_manager"
    scope = data.get("store_scope") or {}
    assert scope.get("mode") == "managed_stores"
    assert store.id in (scope.get("store_ids") or [])
    assert other.id not in (scope.get("store_ids") or [])
    # Managed-store sales only — do not include other store's 999
    assert float(data.get("total_sales") or 0) == 40.0
    assert float(data.get("total_purchases") or 0) == 0.0


@pytest.mark.asyncio
async def test_foreign_user_patch_and_delete_404(client):
    ac, seed = client
    headers = await _super(ac, seed)
    beta_user = seed["u2"].id
    patched = await ac.patch(
        f"/api/v1/users/{beta_user}",
        headers=headers,
        json={"full_name": "Hacked"},
    )
    assert patched.status_code == 404
    deleted = await ac.delete(f"/api/v1/users/{beta_user}", headers=headers)
    assert deleted.status_code == 404


@pytest.mark.asyncio
async def test_cashier_cannot_create_users(client):
    ac, _seed = client
    cash = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.post(
        "/api/v1/users",
        headers=cash,
        json={
            "email": "nope@alpha.example.com",
            "full_name": "Nope",
            "password": "SecurePass123!",
            "role": "cashier",
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_tenant_admin_cannot_create_platform_users(client):
    ac, seed = client
    headers = await _super(ac, seed)
    r = await ac.post(
        "/api/v1/platform/users",
        headers=headers,
        json={
            "email": "evil-platform@ribdigi.example.com",
            "full_name": "Evil",
            "password": "SecurePass123!",
            "role": "platform_super_admin",
        },
    )
    assert r.status_code in (401, 403)
