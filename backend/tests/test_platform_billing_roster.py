"""Software-owner billing list: company plan, amount, and term. No payment is recorded."""

from __future__ import annotations

import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, platform_owner_headers

pytestmark = pytest.mark.asyncio

HIDDEN = ("secret", "webhook", "gateway", "paystack", "authorization", "invoice")


async def _finance(client, seed, db_session):
    db_session.add(
        m.User(
            tenant_id=seed["t1"].id,
            email="billing-finance@alpha.example.com",
            full_name="Billing Finance",
            password_hash=hash_password("SecurePass123!"),
            role="platform_finance",
            email_verified=True,
            permissions=permissions_for_role("platform_finance"),
            is_active=True,
        )
    )
    await db_session.commit()
    return await auth_headers(client, email="billing-finance@alpha.example.com", tenant_slug="alpha")


async def test_finance_sees_company_plans_without_secrets(client, db_session):
    ac, seed = client
    db_session.add(
        m.Tenant(
            slug="platform",
            company_name="Ribdigi House",
            status="active",
            industry="software",
        )
    )
    await db_session.commit()
    headers = await _finance(ac, seed, db_session)
    listed = await ac.get("/api/v1/platform/billing/companies", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.text.lower()
    for needle in HIDDEN:
        assert needle not in body
    rows = {row["company_name"]: row for row in listed.json()["data"]}
    assert "Alpha Co" in rows
    assert "Beta Co" in rows
    assert "Ribdigi House" not in rows
    alpha = rows["Alpha Co"]
    assert alpha["plan"] == "Professional"
    assert alpha["package_code"] == "professional"
    assert alpha["amount"] == 499.0
    assert alpha["currency"] == "GHS"
    assert alpha["status"] == "active"
    assert "id" not in alpha
    assert set(alpha) == {
        "company_name",
        "slug",
        "plan",
        "package_code",
        "amount",
        "currency",
        "term_value",
        "term_unit",
        "status",
        "renews",
    }


async def test_company_admin_cannot_open_platform_billing(client, db_session):
    del db_session
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/platform/billing/companies", headers=admin)
    assert denied.status_code == 403, denied.text


async def test_assign_package_updates_the_list_and_does_not_pay(client, db_session):
    del db_session
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    before = await ac.get("/api/v1/platform/billing/companies", headers=owner)
    assert before.status_code == 200, before.text
    assigned = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={"package_code": "starter", "term_value": 6, "term_unit": "months", "activate": True},
    )
    assert assigned.status_code == 200, assigned.text
    listed = await ac.get("/api/v1/platform/billing/companies", headers=owner)
    alpha = next(row for row in listed.json()["data"] if row["slug"] == "alpha")
    assert alpha["plan"] == "Starter"
    assert alpha["package_code"] == "starter"
    assert alpha["amount"] == 199.0
    assert alpha["term_value"] == 6
    assert alpha["term_unit"] == "months"
    assert alpha["status"] == "active"
    assert "paid" not in listed.text.lower()


@pytest.mark.parametrize("amount", [0, -10, "nan", "", "abc", None])
async def test_paid_assign_rejects_invalid_amount(client, db_session, amount):
    del db_session
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    assigned = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={
            "package_code": "professional",
            "term_value": 1,
            "term_unit": "months",
            "activate": True,
            "amount": amount,
        },
    )
    assert assigned.status_code == 422, assigned.text


async def test_assigned_amount_is_listed_and_only_that_tenant_sees_it(client, db_session):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    assigned = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={
            "package_code": "starter",
            "term_value": 6,
            "term_unit": "months",
            "activate": True,
            "amount": 321,
        },
    )
    assert assigned.status_code == 200, assigned.text
    listed = await ac.get("/api/v1/platform/billing/companies", headers=owner)
    alpha = next(row for row in listed.json()["data"] if row["slug"] == "alpha")
    assert alpha["plan"] == "Starter"
    assert alpha["amount"] == 321.0
    assert alpha["term_value"] == 6
    assert "paid" not in listed.text.lower()

    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    invoices = await ac.get("/api/v1/billing/invoices", headers=admin)
    assert invoices.status_code == 200, invoices.text
    assert all(row.get("status") != "paid" for row in invoices.json()["data"])

    kept = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={"package_code": "starter", "term_value": 6, "term_unit": "months", "activate": True},
    )
    assert kept.status_code == 200, kept.text
    listed_again = await ac.get("/api/v1/platform/billing/companies", headers=owner)
    alpha_again = next(row for row in listed_again.json()["data"] if row["slug"] == "alpha")
    assert alpha_again["amount"] == 321.0

    db_session.add(
        m.User(
            tenant_id=seed["t2"].id,
            email="admin@beta.example.com",
            full_name="Beta Admin",
            password_hash=hash_password("SecurePass123!"),
            role="company_admin",
            email_verified=True,
            permissions=permissions_for_role("company_admin"),
            is_active=True,
        )
    )
    await db_session.commit()
    beta = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    beta_account = await ac.get("/api/v1/billing/account", headers=beta)
    assert beta_account.status_code == 200, beta_account.text
    assert "321" not in beta_account.text
    alpha_account = await ac.get("/api/v1/billing/account", headers=admin)
    assert alpha_account.status_code == 200, alpha_account.text
    assert alpha_account.json()["data"]["plan"]["amount"] == 321.0


async def test_trial_amount_may_be_zero(client, db_session):
    del db_session
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    assigned = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={
            "package_code": "trial",
            "term_value": 1,
            "term_unit": "months",
            "activate": True,
            "amount": 0,
        },
    )
    assert assigned.status_code == 200, assigned.text
    listed = await ac.get("/api/v1/platform/billing/companies", headers=owner)
    alpha = next(row for row in listed.json()["data"] if row["slug"] == "alpha")
    assert alpha["package_code"] == "trial"
    assert alpha["amount"] == 0.0
    assert "paid" not in listed.text.lower()


async def test_created_package_assigns_that_price_and_name(client, db_session):
    del db_session
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    created = await ac.post(
        "/api/v1/platform/billing/plans",
        headers=owner,
        json={
            "code": "hotel-yearly",
            "package_code": "professional",
            "name": "Hotel yearly",
            "interval": "year",
            "amount": "1200.00",
            "currency": "GHS",
        },
    )
    assert created.status_code == 200, created.text
    assigned = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={
            "package_code": "professional",
            "term_value": 1,
            "term_unit": "years",
            "activate": True,
            "amount": 1200,
            "plan_code": "hotel-yearly",
        },
    )
    assert assigned.status_code == 200, assigned.text
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    account = await ac.get("/api/v1/billing/account", headers=admin)
    assert account.status_code == 200, account.text
    plan = account.json()["data"]["plan"]
    assert plan["name"] == "Hotel yearly"
    assert plan["amount"] == 1200.0
    mismatch = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={
            "package_code": "professional",
            "term_value": 1,
            "term_unit": "months",
            "activate": True,
            "amount": 1200,
            "plan_code": "hotel-yearly",
        },
    )
    assert mismatch.status_code == 422, mismatch.text
    garbage = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={
            "package_code": "professional",
            "term_value": 1,
            "term_unit": "years",
            "activate": True,
            "amount": 1200,
            "plan_code": "http://nope",
        },
    )
    assert garbage.status_code == 422, garbage.text


async def test_owner_can_edit_and_delete_an_unused_package(client, db_session):
    del db_session
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    created = await ac.post(
        "/api/v1/platform/billing/plans",
        headers=owner,
        json={
            "code": "hotel-edit",
            "package_code": "professional",
            "name": "Hotel edit",
            "interval": "month",
            "amount": "80.00",
            "currency": "GHS",
        },
    )
    assert created.status_code == 200, created.text
    plan_id = created.json()["data"]["id"]
    edited = await ac.patch(
        f"/api/v1/platform/billing/plans/{plan_id}",
        headers=owner,
        json={"name": "Hotel edited", "amount": "90.00", "package_code": "starter", "interval": "year"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["data"]["name"] == "Hotel edited"
    assert edited.json()["data"]["amount"] == 90.0
    assert edited.json()["data"]["package_code"] == "starter"
    assert edited.json()["data"]["interval"] == "year"
    removed = await ac.delete(f"/api/v1/platform/billing/plans/{plan_id}", headers=owner)
    assert removed.status_code == 200, removed.text
    listed = await ac.get("/api/v1/platform/billing/plans", headers=owner)
    assert listed.status_code == 200, listed.text
    assert all(row["id"] != plan_id for row in listed.json()["data"])


async def test_assigned_package_cannot_be_deleted(client, db_session):
    del db_session
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    created = await ac.post(
        "/api/v1/platform/billing/plans",
        headers=owner,
        json={
            "code": "hotel-kept",
            "package_code": "professional",
            "name": "Hotel kept",
            "interval": "year",
            "amount": "1100.00",
            "currency": "GHS",
        },
    )
    assert created.status_code == 200, created.text
    plan_id = created.json()["data"]["id"]
    assigned = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={
            "package_code": "professional",
            "term_value": 1,
            "term_unit": "years",
            "activate": True,
            "amount": 1100,
            "plan_code": "hotel-kept",
        },
    )
    assert assigned.status_code == 200, assigned.text
    blocked = await ac.delete(f"/api/v1/platform/billing/plans/{plan_id}", headers=owner)
    assert blocked.status_code == 409, blocked.text
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.delete(f"/api/v1/platform/billing/plans/{plan_id}", headers=admin)
    assert denied.status_code == 403, denied.text
