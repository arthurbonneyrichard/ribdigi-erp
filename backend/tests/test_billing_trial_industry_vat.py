"""Strict 14-day trial, package prices per industry, and the software owner's VAT."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app import models as m
from app import saas_billing as billing_svc
from app import tenants as tenants_svc
from app.billing_gateway import MockGateway
from app import db as db_mod
from tests.conftest import auth_headers, platform_owner_headers

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_mock_charges():
    MockGateway._charged.clear()
    yield
    MockGateway._charged.clear()


# ---- Strict 14-day trial ----------------------------------------------------------


def test_trial_is_fixed_at_14_days():
    assert tenants_svc.TRIAL_DAYS == 14
    start = datetime(2026, 1, 1)
    assert tenants_svc.default_trial_ends_at(start) == start + timedelta(days=14)


async def test_owner_cannot_extend_trial_past_14_days(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    too_late = (datetime.utcnow() + timedelta(days=30)).isoformat()
    refused = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "starter-month", "trial_ends_at": too_late},
        headers=owner,
    )
    assert refused.status_code == 422, refused.text
    assert refused.json()["detail"]["code"] == "TRIAL_IS_14_DAYS"
    inside = (datetime.utcnow() + timedelta(days=5)).isoformat()
    ok = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "starter-month", "trial_ends_at": inside},
        headers=owner,
    )
    assert ok.status_code == 200, ok.text


async def test_trial_package_never_runs_past_14_days(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    res = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={"package_code": "trial", "term_value": 12, "term_unit": "months", "activate": True},
    )
    assert res.status_code == 200, res.text
    async with db_mod.SessionLocal() as db:
        tenant = await db.get(m.Tenant, seed["t1"].id)
        latest = tenants_svc.trial_window_end(tenant)
        assert tenant.status == "trial"
        assert tenant.trial_ends_at <= latest + timedelta(seconds=1)
        assert tenant.subscription_ends_at <= latest + timedelta(seconds=1)


async def test_used_trial_cannot_be_given_again(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    async with db_mod.SessionLocal() as db:
        tenant = await db.get(m.Tenant, seed["t1"].id)
        tenant.created_at = datetime.utcnow() - timedelta(days=40)
        await db.commit()
    res = await ac.post(
        "/api/v1/tenants/alpha/subscription",
        headers=owner,
        json={"package_code": "trial", "term_value": 1, "term_unit": "months", "activate": True},
    )
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["code"] == "TRIAL_ALREADY_USED"


async def test_plan_trial_days_capped_at_14(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    res = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "long-trial-month",
            "package_code": "starter",
            "name": "Long trial",
            "interval": "month",
            "amount": "10.00",
            "currency": "GHS",
            "trial_days": 30,
        },
        headers=owner,
    )
    assert res.status_code == 422, res.text


# ---- Industry prices --------------------------------------------------------------


async def test_industry_plans_seeded_and_listed(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    res = await ac.get("/api/v1/platform/billing/plans", headers=owner)
    assert res.status_code == 200, res.text
    by_code = {row["code"]: row for row in res.json()["data"]}
    assert by_code["starter-month"]["industry"] is None
    assert by_code["starter-month-hotel"]["industry"] == "hotel"
    assert by_code["starter-month-hotel"]["amount"] != by_code["starter-month"]["amount"]
    assert by_code["professional-year-restaurant"]["amount"] == 5990.0


async def test_catalog_picks_own_industry_then_general(client):
    del client
    async with db_mod.SessionLocal() as db:
        hotel = await billing_svc.plan_for_package(db, "starter", "months", "hotel")
        retail = await billing_svc.plan_for_package(db, "starter", "months", "retail")
        unknown = await billing_svc.plan_for_package(db, "starter", "months", None)
    assert hotel.code == "starter-month-hotel"
    assert retail.code == "starter-month"
    assert unknown.code == "starter-month"


async def test_other_industry_price_refused(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    res = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "starter-month-hotel"},
        headers=owner,
    )
    # alpha is not a hotel
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["code"] == "PLAN_INDUSTRY_MISMATCH"


async def test_plan_industry_must_be_known(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    res = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "spa-month",
            "package_code": "starter",
            "industry": "spa",
            "name": "Spa monthly",
            "interval": "month",
            "amount": "10.00",
            "currency": "GHS",
        },
        headers=owner,
    )
    assert res.status_code == 422, res.text


# ---- Software owner's VAT ---------------------------------------------------------


def test_split_tax_exclusive_and_inclusive():
    tax = m.PlatformBillingTax(id="default", enabled=True, rate=Decimal("20"), label="VAT", prices_include_tax=False)
    on_top = billing_svc.split_tax(Decimal("100"), "GHS", tax)
    assert (on_top.net, on_top.tax, on_top.gross) == (Decimal("100.00"), Decimal("20.00"), Decimal("120.00"))
    tax.prices_include_tax = True
    inside = billing_svc.split_tax(Decimal("120"), "GHS", tax)
    assert (inside.net, inside.tax, inside.gross) == (Decimal("100.00"), Decimal("20.00"), Decimal("120.00"))
    tax.enabled = False
    off = billing_svc.split_tax(Decimal("120"), "GHS", tax)
    assert off.tax == Decimal("0.00") and off.gross == Decimal("120.00")


async def test_vat_settings_owner_only_and_validated(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.put(
        "/api/v1/platform/billing/tax",
        json={"enabled": True, "rate": "20"},
        headers=admin,
    )
    assert denied.status_code == 403
    zero = await ac.put("/api/v1/platform/billing/tax", json={"enabled": True, "rate": "0"}, headers=owner)
    assert zero.status_code == 422
    saved = await ac.put(
        "/api/v1/platform/billing/tax",
        json={"enabled": True, "rate": "20", "label": "VAT", "registration_number": "C0001234567"},
        headers=owner,
    )
    assert saved.status_code == 200, saved.text
    body = (await ac.get("/api/v1/platform/billing/tax", headers=owner)).json()["data"]
    assert body["enabled"] is True and body["rate"] == 20.0
    assert body["registration_number"] == "C0001234567"


async def test_vat_added_to_company_price_consent_and_invoice(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    saved = await ac.put("/api/v1/platform/billing/tax", json={"enabled": True, "rate": "20"}, headers=owner)
    assert saved.status_code == 200, saved.text
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign", json={"plan_code": "starter-month"}, headers=owner
    )
    assert assigned.status_code == 200, assigned.text

    account = (await ac.get("/api/v1/billing/account", headers=admin)).json()["data"]
    plan = account["plan"]
    assert plan["amount"] == 199.0
    assert plan["tax_amount"] == 39.8
    assert plan["total_amount"] == 238.8
    assert account["tax"]["enabled"] is True

    consent = await ac.post(
        "/api/v1/billing/consent", json={"plan_code": "starter-month", "accept": True}, headers=admin
    )
    assert consent.status_code == 200, consent.text
    assert consent.json()["data"]["consent_amount"] == 238.8

    paid = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/payments",
        json={"amount": "238.80", "currency": "GHS", "reference": "BANK-REF-77"},
        headers=owner,
    )
    assert paid.status_code == 200, paid.text
    inv = paid.json()["data"]
    assert inv["amount"] == 238.8
    assert inv["net_amount"] == 199.0
    assert inv["tax_amount"] == 39.8
    assert inv["tax_rate"] == 20.0

    short = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/payments",
        json={"amount": "199.00", "currency": "GHS", "reference": "BANK-REF-78"},
        headers=owner,
    )
    assert short.status_code == 422


async def test_checkout_refused_when_vat_changed_after_consent(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    await ac.post("/api/v1/platform/billing/tenants/alpha/assign", json={"plan_code": "starter-month"}, headers=owner)
    consent = await ac.post(
        "/api/v1/billing/consent", json={"plan_code": "starter-month", "accept": True}, headers=admin
    )
    assert consent.status_code == 200, consent.text
    await ac.put("/api/v1/platform/billing/tax", json={"enabled": True, "rate": "20"}, headers=owner)
    res = await ac.post("/api/v1/billing/checkout", json={"plan_code": "starter-month"}, headers=admin)
    assert res.status_code == 422, res.text
    assert res.json()["detail"]["code"] == "PRICE_CHANGED_RECONSENT"
    async with db_mod.SessionLocal() as db:
        rows = (await db.execute(select(m.TenantBillingInvoice))).scalars().all()
    assert rows == []
