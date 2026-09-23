"""POST /tenants — create, validation, auth, rollback, isolation."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, platform_owner_headers

PAYLOAD = {
    "company_name": "Retail Demo",
    "slug": "retail-demo",
    "industry": "retail",
    "currency": "GHS",
    "admin_email": "retail.admin@example.com",
    "admin_password": "SecurePass123!",
}


@pytest.mark.asyncio
async def test_create_tenant_unauthorized_without_token(client):
    ac, _seed = client
    denied = await ac.post("/api/v1/tenants", json=PAYLOAD)
    assert denied.status_code == 401, denied.text


@pytest.mark.asyncio
async def test_create_tenant_company_admin_forbidden(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "company-admin-denied"},
    )
    assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
async def test_create_tenant_success(client):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    ok = await ac.post("/api/v1/tenants", headers=headers, json=PAYLOAD)
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["slug"] == "retail-demo"
    assert data["status"] == "trial"
    assert data["tenant_id"]
    assert data["id"] == data["tenant_id"]
    assert data["admin_email_verified"] is False


@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug(client):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    first = await ac.post("/api/v1/tenants", headers=headers, json=PAYLOAD)
    assert first.status_code == 200, first.text
    dup = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "admin_email": "other.admin@example.com"},
    )
    assert dup.status_code == 409, dup.text
    assert "slug" in dup.json()["detail"].lower() or "exists" in dup.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_tenant_same_email_different_slug_is_isolated(client):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    first = await ac.post("/api/v1/tenants", headers=headers, json=PAYLOAD)
    assert first.status_code == 200, first.text
    second = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "retail-demo-two", "company_name": "Retail Demo Two"},
    )
    assert second.status_code == 200, second.text
    assert first.json()["data"]["tenant_id"] != second.json()["data"]["tenant_id"]


@pytest.mark.asyncio
async def test_create_tenant_invalid_industry_and_currency(client):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    bad_ind = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "bad-industry-tenant", "industry": "spaceships"},
    )
    assert bad_ind.status_code == 422, bad_ind.text
    bad_cur = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "bad-currency-tenant", "currency": "NOTISO"},
    )
    assert bad_cur.status_code == 422, bad_cur.text
    weak = await ac.post(
        "/api/v1/tenants",
        headers=headers,
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
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)

    async def boom(*_a, **_k):
        raise RuntimeError("seed failed")

    monkeypatch.setattr("app.api.seed_tenant_defaults", boom)
    failed = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "rollback-demo", "admin_email": "rollback@example.com"},
    )
    assert failed.status_code == 500, failed.text
    assert "Could not create the workspace" in failed.json()["detail"]

    monkeypatch.undo()
    retry = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "rollback-demo", "admin_email": "rollback@example.com"},
    )
    assert retry.status_code == 200, retry.text


@pytest.mark.asyncio
async def test_create_tenant_email_send_failure_still_persists(client, monkeypatch):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)

    async def boom(*_a, **_k):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("app.emailer.send_email", boom)
    ok = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "email-fail-co", "admin_email": "email.fail@example.com"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["slug"] == "email-fail-co"
    assert ok.json()["data"]["email"]["sent"] is False


@pytest.mark.asyncio
async def test_created_tenant_cannot_read_other_tenant_products(client):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    created = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={
            **PAYLOAD,
            "slug": "iso-retail",
            "admin_email": "iso.admin@example.com",
        },
    )
    assert created.status_code == 200, created.text
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    other = await ac.get(f"/api/v1/products/{seed['p2'].id}", headers=cashier)
    assert other.status_code in {403, 404}, other.text
    own = await ac.get(f"/api/v1/products/{seed['p1'].id}", headers=cashier)
    assert own.status_code == 200, own.text


@pytest.mark.asyncio
async def test_create_tenant_rollback_leaves_no_user_row(client, db_session, monkeypatch):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)

    async def boom(*_a, **_k):
        raise RuntimeError("seed failed")

    monkeypatch.setattr("app.api.seed_tenant_defaults", boom)
    await ac.post(
        "/api/v1/tenants",
        headers=headers,
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


@pytest.mark.asyncio
async def test_create_tenant_seed_step_returns_named_error(client, monkeypatch):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)

    async def boom(*_a, **_k):
        raise RuntimeError("accounts insert failed")

    monkeypatch.setattr("app.accounting.ensure_default_accounts", boom)
    failed = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "seed-coa-fail", "admin_email": "seed.coa@example.com"},
    )
    assert failed.status_code == 500, failed.text
    assert "chart of accounts" in failed.json()["detail"]
    assert "Nothing was saved" in failed.json()["detail"]


def test_tenant_create_failure_maps_programming_error():
    from sqlalchemy.exc import ProgrammingError

    from app.http_errors import TENANT_CREATE_SCHEMA, http_exception_for_tenant_create_failure

    exc = ProgrammingError("INSERT", {}, Exception("column foo does not exist"))
    mapped = http_exception_for_tenant_create_failure(exc)
    assert mapped.status_code == 500
    assert mapped.detail == TENANT_CREATE_SCHEMA


def test_tenant_create_seed_integrity_is_not_slug_conflict():
    from sqlalchemy.exc import IntegrityError

    from app.http_errors import TenantSeedError, http_exception_for_tenant_create_failure

    cause = IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: accounts.code"))
    wrapped = TenantSeedError("chart of accounts")
    wrapped.__cause__ = cause
    mapped = http_exception_for_tenant_create_failure(wrapped)
    assert mapped.status_code == 500
    assert "chart of accounts" in mapped.detail
    assert "slug" not in mapped.detail.lower()


@pytest.mark.asyncio
async def test_create_tenant_seeds_coa_without_opening_balance_column(client, db_session):
    await db_session.execute(text("ALTER TABLE accounts DROP COLUMN opening_balance"))
    await db_session.commit()
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    ok = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "coa-no-open", "admin_email": "coa.noopen@example.com"},
    )
    assert ok.status_code == 200, ok.text
    codes = (
        await db_session.execute(
            text("SELECT code FROM accounts WHERE tenant_id = (SELECT id FROM tenants WHERE slug = :slug)"),
            {"slug": "coa-no-open"},
        )
    ).scalars().all()
    assert "1000" in codes
    assert "1010" in codes


@pytest.mark.asyncio
async def test_create_tenant_seeds_coa_when_is_system_is_required(client, db_session):
    await db_session.execute(text("ALTER TABLE accounts ADD COLUMN is_system BOOLEAN NOT NULL DEFAULT 0"))
    await db_session.commit()
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    ok = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "coa-is-system", "admin_email": "coa.system@example.com"},
    )
    assert ok.status_code == 200, ok.text
    flagged = (
        await db_session.execute(
            text(
                "SELECT is_system FROM accounts WHERE tenant_id = "
                "(SELECT id FROM tenants WHERE slug = :slug) AND code = '1000'"
            ),
            {"slug": "coa-is-system"},
        )
    ).scalar_one()
    assert bool(flagged) is True


@pytest.mark.asyncio
async def test_create_tenant_retry_does_not_duplicate_slug(client):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    first = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "retry-slug", "admin_email": "retry.one@example.com"},
    )
    assert first.status_code == 200, first.text
    second = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "retry-slug", "admin_email": "retry.two@example.com"},
    )
    assert second.status_code == 409, second.text


@pytest.mark.asyncio
async def test_create_tenant_seeds_welcome_with_optional_company_id(client, db_session):
    await db_session.execute(text("ALTER TABLE notifications ADD COLUMN company_id VARCHAR(36)"))
    await db_session.commit()
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    ok = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "welcome-co", "admin_email": "welcome.co@example.com"},
    )
    assert ok.status_code == 200, ok.text
    titles = (
        await db_session.execute(
            text(
                "SELECT title FROM notifications WHERE tenant_id = "
                "(SELECT id FROM tenants WHERE slug = :slug)"
            ),
            {"slug": "welcome-co"},
        )
    ).scalars().all()
    assert any("Welcome" in (t or "") for t in titles)


@pytest.mark.asyncio
async def test_create_tenant_succeeds_when_welcome_notification_insert_fails(
    client, db_session, monkeypatch
):
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)

    async def boom(*_a, **_k):
        raise RuntimeError("notifications insert failed")

    monkeypatch.setattr("app.notifications.create_notification", boom)
    ok = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "welcome-skip", "admin_email": "welcome.skip@example.com"},
    )
    assert ok.status_code == 200, ok.text
    leftover = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "welcome-skip"))
    ).scalar_one_or_none()
    assert leftover is not None


@pytest.mark.asyncio
async def test_create_tenant_continues_after_welcome_integrity_error(client, db_session, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    ac, seed = client
    headers = await platform_owner_headers(ac, seed)

    async def boom(*_a, **_k):
        raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed: notifications.id"))

    monkeypatch.setattr("app.notifications.create_notification", boom)
    ok = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "welcome-integ", "admin_email": "welcome.integ@example.com"},
    )
    assert ok.status_code == 200, ok.text
    vat = (
        await db_session.execute(
            text(
                "SELECT name FROM tax_rates WHERE tenant_id = "
                "(SELECT id FROM tenants WHERE slug = :slug)"
            ),
            {"slug": "welcome-integ"},
        )
    ).scalars().all()
    assert "VAT" in vat


@pytest.mark.asyncio
async def test_create_tenant_seeds_tax_when_code_is_required(client, db_session):
    await db_session.execute(text("ALTER TABLE tax_rates ADD COLUMN code VARCHAR(40) NOT NULL DEFAULT 'TAX'"))
    await db_session.commit()
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    ok = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "tax-code", "admin_email": "tax.code@example.com"},
    )
    assert ok.status_code == 200, ok.text
    codes = (
        await db_session.execute(
            text(
                "SELECT code FROM tax_rates WHERE tenant_id = "
                "(SELECT id FROM tenants WHERE slug = :slug)"
            ),
            {"slug": "tax-code"},
        )
    ).scalars().all()
    assert "VAT" in codes


@pytest.mark.asyncio
async def test_create_tenant_seeds_units_with_conversion_factor(client, db_session):
    await db_session.execute(text("ALTER TABLE units_of_measure ADD COLUMN conversion_factor NUMERIC NOT NULL DEFAULT 1"))
    await db_session.commit()
    ac, seed = client
    headers = await platform_owner_headers(ac, seed)
    ok = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={**PAYLOAD, "slug": "uom-factor", "admin_email": "uom.factor@example.com"},
    )
    assert ok.status_code == 200, ok.text
