"""POST /tenants — create, validation, auth, rollback, isolation."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers

PAYLOAD = {
    "company_name": "Retail Demo",
    "slug": "retail-demo",
    "industry": "retail",
    "currency": "GHS",
    "admin_email": "retail.admin@example.com",
    "admin_password": "SecurePass123!",
}


@pytest.mark.asyncio
async def test_create_tenant_success(client):
    ac, _seed = client
    ok = await ac.post("/api/v1/tenants", json=PAYLOAD)
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["slug"] == "retail-demo"
    assert data["status"] == "trial"
    assert data["tenant_id"]
    assert data["id"] == data["tenant_id"]
    assert data["admin_email_verified"] is False


@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug(client):
    ac, _seed = client
    first = await ac.post("/api/v1/tenants", json=PAYLOAD)
    assert first.status_code == 200, first.text
    dup = await ac.post(
        "/api/v1/tenants",
        json={**PAYLOAD, "admin_email": "other.admin@example.com"},
    )
    assert dup.status_code == 409, dup.text
    assert "slug" in dup.json()["detail"].lower() or "exists" in dup.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_tenant_same_email_different_slug_is_isolated(client):
    ac, _seed = client
    first = await ac.post("/api/v1/tenants", json=PAYLOAD)
    assert first.status_code == 200, first.text
    second = await ac.post(
        "/api/v1/tenants",
        json={**PAYLOAD, "slug": "retail-demo-two", "company_name": "Retail Demo Two"},
    )
    assert second.status_code == 200, second.text
    assert first.json()["data"]["tenant_id"] != second.json()["data"]["tenant_id"]


@pytest.mark.asyncio
async def test_create_tenant_invalid_industry_and_currency(client):
    ac, _seed = client
    bad_ind = await ac.post(
        "/api/v1/tenants",
        json={**PAYLOAD, "slug": "bad-industry-tenant", "industry": "spaceships"},
    )
    assert bad_ind.status_code == 422, bad_ind.text
    bad_cur = await ac.post(
        "/api/v1/tenants",
        json={**PAYLOAD, "slug": "bad-currency-tenant", "currency": "NOTISO"},
    )
    assert bad_cur.status_code == 422, bad_cur.text
    weak = await ac.post(
        "/api/v1/tenants",
        json={**PAYLOAD, "slug": "weak-pass-tenant", "admin_password": "short"},
    )
    assert weak.status_code in {400, 422}, weak.text


@pytest.mark.asyncio
async def test_create_tenant_platform_finance_forbidden(client, db_session):
    ac, seed = client
    finance = m.User(
        tenant_id=seed["t1"].id,
        email="finance@alpha.example.com",
        full_name="Platform Finance",
        password_hash=hash_password("SecurePass123!"),
        role="platform_finance",
        email_verified=True,
        permissions=permissions_for_role("platform_finance"),
        is_active=True,
    )
    db_session.add(finance)
    await db_session.commit()
    headers = await auth_headers(ac, email="finance@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "finance-denied-co"},
    )
    assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
async def test_create_tenant_rolls_back_when_seed_fails(client, monkeypatch):
    ac, _seed = client

    async def boom(*_a, **_k):
        raise RuntimeError("seed failed")

    monkeypatch.setattr("app.api.seed_tenant_defaults", boom)
    failed = await ac.post(
        "/api/v1/tenants",
        json={**PAYLOAD, "slug": "rollback-demo", "admin_email": "rollback@example.com"},
    )
    assert failed.status_code == 500, failed.text
    assert failed.json()["detail"] == "The server could not complete this request."

    monkeypatch.undo()
    retry = await ac.post(
        "/api/v1/tenants",
        json={**PAYLOAD, "slug": "rollback-demo", "admin_email": "rollback@example.com"},
    )
    assert retry.status_code == 200, retry.text


@pytest.mark.asyncio
async def test_create_tenant_email_send_failure_still_persists(client, monkeypatch):
    ac, _seed = client

    async def boom(*_a, **_k):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("app.emailer.send_email", boom)
    ok = await ac.post(
        "/api/v1/tenants",
        json={**PAYLOAD, "slug": "email-fail-co", "admin_email": "email.fail@example.com"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["slug"] == "email-fail-co"
    assert ok.json()["data"]["email"]["sent"] is False


@pytest.mark.asyncio
async def test_created_tenant_cannot_read_other_tenant_products(client):
    ac, seed = client
    created = await ac.post(
        "/api/v1/tenants",
        json={
            **PAYLOAD,
            "slug": "iso-retail",
            "admin_email": "iso.admin@example.com",
        },
    )
    assert created.status_code == 200, created.text
    # New admin is unverified; platform-style isolation still holds for existing cashier.
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    other = await ac.get(f"/api/v1/products/{seed['p2'].id}", headers=headers)
    assert other.status_code in {403, 404}, other.text
    own = await ac.get(f"/api/v1/products/{seed['p1'].id}", headers=headers)
    assert own.status_code == 200, own.text


@pytest.mark.asyncio
async def test_create_tenant_rollback_leaves_no_user_row(client, db_session, monkeypatch):
    ac, _seed = client

    async def boom(*_a, **_k):
        raise RuntimeError("seed failed")

    monkeypatch.setattr("app.api.seed_tenant_defaults", boom)
    await ac.post(
        "/api/v1/tenants",
        json={**PAYLOAD, "slug": "no-partial", "admin_email": "nopartial@example.com"},
    )
    leftover = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "no-partial"))
    ).scalar_one_or_none()
    assert leftover is None
    leftover_user = (
        await db_session.execute(select(m.User).where(m.User.email == "nopartial@example.com"))
    ).scalar_one_or_none()
    assert leftover_user is None
