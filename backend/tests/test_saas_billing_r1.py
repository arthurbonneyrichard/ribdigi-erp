"""SaaS subscription renewals. Mock gateway only — no live charges."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app import models as m
from app.billing_gateway import ChargeResult, MockGateway, sign_mock_webhook
from app.config import settings
from app import jobs as jobs_mod
from app.jobs import job_process_subscription_renewals, job_scan_trial_lifecycle
from app.saas_billing import process_due_renewals
from app.schemas import CustomerPaymentCreate, PosSaleCreate
from tests.conftest import auth_headers, platform_owner_headers

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clear_mock_charges():
    MockGateway._charged.clear()
    yield
    MockGateway._charged.clear()


async def _admin(client, seed):
    return await auth_headers(client, email="admin@alpha.example.com", tenant_slug="alpha")


async def _authorize(client, seed, headers, *, plan="professional-month", token="mock_auth_ok_safe1", renewal=None, trial=None):
    owner = await platform_owner_headers(client, seed)
    body = {"plan_code": plan}
    if renewal:
        body["next_renewal_at"] = renewal
    if trial:
        body["trial_ends_at"] = trial
    assigned = await client.post("/api/v1/platform/billing/tenants/alpha/assign", json=body, headers=owner)
    assert assigned.status_code == 200, assigned.text
    consent = await client.post(
        "/api/v1/billing/consent",
        json={"plan_code": plan, "accept": True},
        headers=headers,
    )
    assert consent.status_code == 200, consent.text
    saved = await client.post(
        "/api/v1/billing/sandbox/authorize",
        json={"authorization_code": token},
        headers=headers,
    )
    assert saved.status_code == 200, saved.text
    account = saved.json()["data"]
    assert account["authorization_present"] is True
    assert token not in saved.text
    assert account["consent_version"] == "saas-billing-v1"
    return account


async def _invoice_count(tenant_id: str) -> int:
    async with jobs_mod.SessionLocal() as db:
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(m.TenantBillingInvoice).where(
                        m.TenantBillingInvoice.tenant_id == tenant_id
                    )
                )
            ).scalar_one()
        )


async def _attempt_count(tenant_id: str) -> int:
    async with jobs_mod.SessionLocal() as db:
        return int(
            (
                await db.execute(
                    select(func.count()).select_from(m.TenantBillingAttempt).where(
                        m.TenantBillingAttempt.tenant_id == tenant_id
                    )
                )
            ).scalar_one()
        )


async def test_consented_renewal_charges_once(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    await _authorize(ac, seed, headers, renewal=past)
    first = await job_process_subscription_renewals()
    second = await job_process_subscription_renewals()
    assert first["ok"] is True
    assert first["charged"] == 1
    assert second["ok"] is True
    assert second["charged"] == 0
    assert len(MockGateway._charged) == 1
    invoices = await ac.get("/api/v1/billing/invoices", headers=headers)
    assert invoices.status_code == 200, invoices.text
    rows = invoices.json()["data"]
    assert len(rows) == 1
    assert rows[0]["status"] == "paid"
    assert rows[0]["currency"] == "GHS"
    assert rows[0]["amount"] == 499
    assert rows[0]["description"] == "Professional monthly subscription"
    assert rows[0]["period_end"]
    account = await ac.get("/api/v1/billing/account", headers=headers)
    body = account.json()["data"]
    assert body["billing_status"] == "active"
    assert body["auto_renew"] is True
    assert body["paid_through"]
    returned = await ac.get("/api/v1/billing/checkout/return?reference=browser", headers=headers)
    assert returned.json()["data"]["confirmed_by_redirect"] is False


async def test_trial_without_token_is_not_charged(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    owner = await platform_owner_headers(ac, seed)
    past = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "starter-month", "trial_ends_at": past},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    outcome = await job_scan_trial_lifecycle()
    assert outcome["ok"] is True
    assert await _invoice_count(seed["t1"].id) == 0
    assert MockGateway._charged == set()
    account = await ac.get("/api/v1/billing/account", headers=headers)
    body = account.json()["data"]
    assert body["billing_status"] == "payment_required"
    assert body["authorization_present"] is False
    assert "/company/billing" in body["checkout_path"]
    async with jobs_mod.SessionLocal() as db:
        owner_notes = (
            await db.execute(
                select(m.Notification).where(
                    m.Notification.user_id == seed["super"].id,
                    m.Notification.category == "billing",
                )
            )
        ).scalars().all()
    assert any(note.title == "Trial ended — payment required" for note in owner_notes)
    assert all("mock_auth_" not in (note.message or "") for note in owner_notes)
    assert any("Alpha Co" in (note.message or "") for note in owner_notes)
    checkout = await ac.post(
        "/api/v1/billing/checkout",
        json={"plan_code": "starter-month"},
        headers=headers,
    )
    assert checkout.status_code == 422


async def test_duplicate_webhook_does_not_duplicate_invoice(client, monkeypatch):
    ac, seed = client
    monkeypatch.setattr(settings, "BILLING_WEBHOOK_SECRET", "sandbox-webhook-secret-value")
    headers = await _admin(ac, seed)
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    await _authorize(ac, seed, headers, renewal=past)
    assert (await job_process_subscription_renewals())["charged"] == 1
    invoices = (await ac.get("/api/v1/billing/invoices", headers=headers)).json()["data"]
    assert len(invoices) == 1
    event = {
        "id": "evt-renew-1",
        "event": "charge.success",
        "data": {
            "reference": invoices[0]["idempotency_key"],
            "amount": 49900,
            "currency": "GHS",
            "tenant_id": seed["t1"].id,
            "gateway_reference": "mock_tx_once",
        },
    }
    raw = json.dumps(event, separators=(",", ":")).encode()
    signature = sign_mock_webhook(raw)
    headers_hook = {"x-ribdigi-billing-signature": signature, "content-type": "application/json"}
    first = await ac.post("/api/v1/billing/webhooks/mock", content=raw, headers=headers_hook)
    second = await ac.post("/api/v1/billing/webhooks/mock", content=raw, headers=headers_hook)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["duplicate"] is False
    assert second.json()["data"]["duplicate"] is True
    mismatch = {
        "id": "evt-renew-mismatch",
        "event": "charge.success",
        "data": {
            "reference": invoices[0]["idempotency_key"],
            "amount": 100,
            "currency": "USD",
            "tenant_id": seed["t2"].id,
        },
    }
    raw_bad = json.dumps(mismatch, separators=(",", ":")).encode()
    bad = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw_bad,
        headers={"x-ribdigi-billing-signature": sign_mock_webhook(raw_bad), "content-type": "application/json"},
    )
    assert bad.status_code == 200
    assert bad.json()["data"]["outcome"] == "mismatch"
    unsigned = await ac.post("/api/v1/billing/webhooks/mock", content=raw, headers={"content-type": "application/json"})
    assert unsigned.status_code == 401
    again = (await ac.get("/api/v1/billing/invoices", headers=headers)).json()["data"]
    assert len(again) == 1
    assert again[0]["status"] == "paid"
    assert len(MockGateway._charged) == 1
    assert (await job_process_subscription_renewals())["charged"] == 0


async def test_failed_charges_follow_retry_and_grace(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    await _authorize(ac, seed, headers, renewal=past, token="mock_auth_fail_card")
    base = datetime.utcnow()
    async with jobs_mod.SessionLocal() as db:
        first = await process_due_renewals(db, now=base)
        await db.commit()
    assert first["failed"] == 1
    assert await _attempt_count(seed["t1"].id) == 1
    async with jobs_mod.SessionLocal() as db:
        immediate = await process_due_renewals(db, now=base)
        await db.commit()
    assert immediate["failed"] == 0
    assert await _attempt_count(seed["t1"].id) == 1
    async with jobs_mod.SessionLocal() as db:
        second = await process_due_renewals(db, now=base + timedelta(days=2))
        await db.commit()
    assert second["failed"] == 1
    assert await _attempt_count(seed["t1"].id) == 2
    third_at = base + timedelta(days=6)
    async with jobs_mod.SessionLocal() as db:
        third = await process_due_renewals(db, now=third_at)
        await db.commit()
    assert third["failed"] == 1
    assert await _attempt_count(seed["t1"].id) == 3
    account = (await ac.get("/api/v1/billing/account", headers=headers)).json()["data"]
    assert account["billing_status"] == "grace_period"
    assert account["tenant_status"] == "grace"
    async with jobs_mod.SessionLocal() as db:
        suspended = await process_due_renewals(db, now=third_at + timedelta(days=8))
        await db.commit()
    assert suspended["suspended"] == 1
    assert await _attempt_count(seed["t1"].id) == 3
    assert await _invoice_count(seed["t1"].id) == 1
    async with jobs_mod.SessionLocal() as db:
        tenant = await db.get(m.Tenant, seed["t1"].id)
        product = (
            await db.execute(select(m.Product).where(m.Product.tenant_id == seed["t1"].id))
        ).scalar_one()
        assert tenant.status == "suspended"
        assert product.name == "Alpha Widget"
        assert float(product.stock_qty) == 10


async def test_cancel_stops_future_charges_and_keeps_paid_access(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    await _authorize(ac, seed, headers, renewal=past)
    assert (await job_process_subscription_renewals())["charged"] == 1
    canceled = await ac.post("/api/v1/billing/cancel", json={"confirm": True}, headers=headers)
    assert canceled.status_code == 200, canceled.text
    body = canceled.json()["data"]
    assert body["auto_renew"] is False
    assert body["billing_status"] == "canceled"
    assert body["paid_through"]
    async with jobs_mod.SessionLocal() as db:
        account = (
            await db.execute(
                select(m.TenantBillingAccount).where(m.TenantBillingAccount.tenant_id == seed["t1"].id)
            )
        ).scalar_one()
        account.next_renewal_at = datetime.utcnow() - timedelta(days=1)
        await db.commit()
    again = await job_process_subscription_renewals()
    assert again["charged"] == 0
    assert await _invoice_count(seed["t1"].id) == 1
    assert len(MockGateway._charged) == 1
    account_after = (await ac.get("/api/v1/billing/account", headers=headers)).json()["data"]
    assert account_after["tenant_status"] == "active"
    assert account_after["auto_renew"] is False


async def test_tenant_isolation_and_owner_only_plan_management(client):
    ac, seed = client
    admin = await _admin(ac, seed)
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    owner = await platform_owner_headers(ac, seed)
    denied_cashier = await ac.get("/api/v1/billing/account", headers=cashier)
    assert denied_cashier.status_code == 403
    denied_plans = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "custom-month",
            "package_code": "starter",
            "name": "Custom monthly",
            "interval": "month",
            "amount": "10.00",
            "currency": "GHS",
        },
        headers=admin,
    )
    assert denied_plans.status_code == 403
    created = await ac.post(
        "/api/v1/platform/billing/plans",
        json={
            "code": "custom-month",
            "package_code": "starter",
            "name": "Custom monthly",
            "interval": "month",
            "amount": "10.00",
            "currency": "GHS",
            "trial_days": 7,
            "grace_days": 3,
        },
        headers=owner,
    )
    assert created.status_code == 200, created.text
    other = dict(admin)
    other["X-Tenant-ID"] = seed["t2"].id
    cross = await ac.get("/api/v1/billing/account", headers=other)
    assert cross.status_code == 403
    recorded = await ac.post(
        "/api/v1/platform/billing/tenants/beta/assign",
        json={"plan_code": "custom-month"},
        headers=owner,
    )
    assert recorded.status_code == 200, recorded.text
    payment = await ac.post(
        "/api/v1/platform/billing/tenants/beta/payments",
        json={"amount": "10.00", "currency": "GHS", "reference": "manual-beta-1", "note": "Owner recorded"},
        headers=owner,
    )
    assert payment.status_code == 200, payment.text
    alpha_invoices = (await ac.get("/api/v1/billing/invoices", headers=admin)).json()["data"]
    assert alpha_invoices == []
    beta_view = await ac.get("/api/v1/platform/billing/tenants/beta", headers=owner)
    assert beta_view.status_code == 200
    assert beta_view.json()["data"]["invoices"][0]["status"] == "paid"
    admin_beta = await ac.get("/api/v1/platform/billing/tenants/beta", headers=admin)
    assert admin_beta.status_code == 403
    card = await ac.post(
        "/api/v1/platform/billing/tenants/beta/payments",
        json={"amount": "10.00", "currency": "GHS", "reference": "4111111111111111"},
        headers=owner,
    )
    assert card.status_code == 422


async def test_gateway_secrets_are_not_stored_or_returned(client, monkeypatch):
    ac, seed = client
    secret = "sk_test_should_not_leak_value_123456"
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", secret)
    headers = await _admin(ac, seed)
    owner = await platform_owner_headers(ac, seed)
    status = await ac.get("/api/v1/platform/billing/status", headers=owner)
    account = await ac.get("/api/v1/billing/account", headers=headers)
    assert secret not in status.text
    assert secret not in account.text
    names = {column.name for column in m.TenantBillingAccount.__table__.columns}
    names |= {column.name for column in m.TenantBillingInvoice.__table__.columns}
    names |= {column.name for column in m.TenantBillingAttempt.__table__.columns}
    assert names.isdisjoint({"pan", "cvv", "card_number", "card_pan", "online_banking_password"})
    assert "gateway_authorization_ref" not in CustomerPaymentCreate.model_fields
    assert "gateway_authorization_ref" not in PosSaleCreate.model_fields


async def test_tenant_sees_only_assigned_plan_amount(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    before = await ac.get("/api/v1/billing/plans", headers=admin)
    assert before.status_code == 200, before.text
    assert before.json()["data"] == []
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "professional-month", "custom_amount": "250.00", "custom_currency": "GHS"},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    plans = await ac.get("/api/v1/billing/plans", headers=admin)
    assert plans.status_code == 200, plans.text
    rows = plans.json()["data"]
    assert len(rows) == 1
    assert rows[0]["code"] == "professional-month"
    assert rows[0]["amount"] == 250.0
    assert rows[0]["currency"] == "GHS"
    account = await ac.get("/api/v1/billing/account", headers=admin)
    assert account.json()["data"]["plan"]["amount"] == 250.0
    assert account.json()["data"]["plan"]["code"] == "professional-month"
    other = await ac.post(
        "/api/v1/billing/consent",
        json={"plan_code": "starter-month", "accept": True},
        headers=admin,
    )
    assert other.status_code == 422, other.text
    checkout = await ac.post(
        "/api/v1/billing/checkout",
        json={"plan_code": "starter-month"},
        headers=admin,
    )
    assert checkout.status_code == 422, checkout.text
    catalog = await ac.get("/api/v1/platform/billing/plans", headers=admin)
    assert catalog.status_code == 403


async def test_active_company_without_billing_profile_shows_package_only(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    account = await ac.get("/api/v1/billing/account", headers=admin)
    assert account.status_code == 200, account.text
    body = account.json()["data"]
    assert body["tenant_status"] == "active"
    assert body["billing_status"] == "active"
    assert "trial ends" not in body["access_note"].lower()
    assert "read-only" not in body["access_note"].lower()
    assert body["plan"]["name"] == "Professional"
    assert body["plan"]["code"] == ""
    assert body["plan"]["amount"] is None
    plans = await ac.get("/api/v1/billing/plans", headers=admin)
    assert plans.status_code == 200, plans.text
    assert plans.json()["data"] == []
    consent = await ac.post(
        "/api/v1/billing/consent",
        json={"plan_code": "professional-month", "accept": True},
        headers=admin,
    )
    assert consent.status_code == 422, consent.text
    invoices = await ac.get("/api/v1/billing/invoices", headers=admin)
    assert invoices.status_code == 200, invoices.text
    assert invoices.json()["data"] == []


async def test_owner_reactivate_does_not_charge(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/beta/assign",
        json={"plan_code": "starter-month"},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    async with jobs_mod.SessionLocal() as db:
        tenant = await db.get(m.Tenant, seed["t2"].id)
        account = (
            await db.execute(
                select(m.TenantBillingAccount).where(m.TenantBillingAccount.tenant_id == seed["t2"].id)
            )
        ).scalar_one()
        tenant.status = "suspended"
        account.billing_status = "suspended"
        await db.commit()
    restored = await ac.post("/api/v1/platform/billing/tenants/beta/reactivate", headers=owner)
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["charged"] is False
    assert restored.json()["data"]["tenant_status"] == "active"
    assert restored.json()["data"]["billing_status"] == "payment_required"
    assert await _invoice_count(seed["t2"].id) == 0
    assert MockGateway._charged == set()


async def test_trial_reminder_does_not_charge(client):
    ac, seed = client
    owner = await platform_owner_headers(ac, seed)
    trial_end = datetime.utcnow() + timedelta(days=3)
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "starter-month", "trial_ends_at": trial_end.isoformat()},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    async with jobs_mod.SessionLocal() as db:
        first = await process_due_renewals(db, now=datetime.utcnow())
        await db.commit()
    assert first["reminded"] == 1
    assert first["charged"] == 0
    async with jobs_mod.SessionLocal() as db:
        second = await process_due_renewals(db, now=datetime.utcnow())
        titles = (
            await db.execute(
                select(m.Notification.title).where(
                    m.Notification.tenant_id == seed["t1"].id,
                    m.Notification.category == "billing",
                )
            )
        ).scalars().all()
        await db.commit()
    assert second["reminded"] == 0
    assert any(title.startswith("Trial ends in ") for title in titles)
    assert await _invoice_count(seed["t1"].id) == 0
    assert MockGateway._charged == set()


async def test_pending_charge_waits_for_webhook(client, monkeypatch):
    ac, seed = client
    monkeypatch.setattr(settings, "BILLING_WEBHOOK_SECRET", "sandbox-webhook-secret-value")
    headers = await _admin(ac, seed)
    past = (datetime.utcnow() - timedelta(days=1)).isoformat()
    await _authorize(ac, seed, headers, renewal=past)

    class _PendingGateway:
        def charge(self, **kwargs):
            return ChargeResult(False, "gw_pending_1", "pending", pending=True)

    monkeypatch.setattr("app.billing_gateway.get_gateway", lambda: _PendingGateway())
    async with jobs_mod.SessionLocal() as db:
        first = await process_due_renewals(db, now=datetime.utcnow())
        await db.commit()
    assert first["charged"] == 0
    assert first["failed"] == 0
    assert await _attempt_count(seed["t1"].id) == 1
    invoices = (await ac.get("/api/v1/billing/invoices", headers=headers)).json()["data"]
    assert len(invoices) == 1
    assert invoices[0]["status"] == "open"
    async with jobs_mod.SessionLocal() as db:
        second = await process_due_renewals(db, now=datetime.utcnow())
        await db.commit()
    assert second["charged"] == 0
    assert await _attempt_count(seed["t1"].id) == 1
    omitted = {
        "id": "evt-pending-omitted",
        "event": "charge.success",
        "data": {"reference": invoices[0]["idempotency_key"]},
    }
    raw_omitted = json.dumps(omitted, separators=(",", ":")).encode()
    omitted_res = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw_omitted,
        headers={
            "x-ribdigi-billing-signature": sign_mock_webhook(raw_omitted),
            "content-type": "application/json",
        },
    )
    assert omitted_res.status_code == 200, omitted_res.text
    assert omitted_res.json()["data"]["outcome"] == "mismatch"
    still_open = (await ac.get("/api/v1/billing/invoices", headers=headers)).json()["data"]
    assert still_open[0]["status"] == "open"
    event = {
        "id": "evt-pending-fail",
        "event": "charge.failed",
        "data": {
            "reference": invoices[0]["idempotency_key"],
            "amount": 49900,
            "currency": "GHS",
            "tenant_id": seed["t1"].id,
        },
    }
    raw = json.dumps(event, separators=(",", ":")).encode()
    failed = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw,
        headers={"x-ribdigi-billing-signature": sign_mock_webhook(raw), "content-type": "application/json"},
    )
    assert failed.status_code == 200, failed.text
    assert failed.json()["data"]["outcome"] == "failed"
    after = (await ac.get("/api/v1/billing/invoices", headers=headers)).json()["data"]
    assert len(after) == 1
    assert after[0]["status"] == "failed"
    assert MockGateway._charged == set()


async def _post_mock_webhook(ac, event: dict):
    raw = json.dumps(event, separators=(",", ":")).encode()
    response = await ac.post(
        "/api/v1/billing/webhooks/mock",
        content=raw,
        headers={"x-ribdigi-billing-signature": sign_mock_webhook(raw), "content-type": "application/json"},
    )
    assert response.status_code == 200, response.text
    return response


async def test_checkout_return_saves_method_only_after_provider_confirmation(client, monkeypatch):
    """Hosted checkout stays unpaid. A reusable provider confirmation saves the method."""
    ac, seed = client
    monkeypatch.setattr(settings, "BILLING_WEBHOOK_SECRET", "sandbox-webhook-secret-value")
    headers = await _admin(ac, seed)
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    owner = await platform_owner_headers(ac, seed)
    assigned = await ac.post(
        "/api/v1/platform/billing/tenants/alpha/assign",
        json={"plan_code": "professional-month"},
        headers=owner,
    )
    assert assigned.status_code == 200, assigned.text
    consent = await ac.post(
        "/api/v1/billing/consent",
        json={"plan_code": "professional-month", "accept": True},
        headers=headers,
    )
    assert consent.status_code == 200, consent.text
    denied = await ac.post(
        "/api/v1/billing/checkout",
        json={"plan_code": "professional-month"},
        headers=cashier,
    )
    assert denied.status_code == 403
    other_plan = await ac.post(
        "/api/v1/billing/checkout",
        json={"plan_code": "starter-month"},
        headers=headers,
    )
    assert other_plan.status_code == 422
    started = await ac.post(
        "/api/v1/billing/checkout",
        json={"plan_code": "professional-month"},
        headers=headers,
    )
    assert started.status_code == 200, started.text
    checkout = started.json()["data"]
    assert checkout["paid"] is False
    assert checkout["provider"] == "mock"
    assert checkout["checkout_url"]
    reference = checkout["reference"]
    assert reference.startswith("checkout:")
    profile = (await ac.get("/api/v1/billing/account", headers=headers)).json()["data"]
    assert profile["authorization_present"] is False
    assert profile["gateway_provider"] == "mock"
    amount_minor = int(round(float(profile["plan"]["amount"]) * 100))
    currency = profile["plan"]["currency"]
    before = await _invoice_count(seed["t1"].id)
    bare = await ac.get(f"/api/v1/billing/checkout/return?reference={reference}", headers=headers)
    assert bare.status_code == 200, bare.text
    bare_body = bare.json()["data"]
    assert bare_body["confirmed_by_redirect"] is False
    assert bare_body["paid"] is False
    assert bare_body["authorization_present"] is False
    assert bare_body["reference_matches_checkout"] is True
    assert await _invoice_count(seed["t1"].id) == before
    invoices = (await ac.get("/api/v1/billing/invoices", headers=headers)).json()["data"]
    assert all(row["status"] != "paid" for row in invoices)
    omitted_auth = await _post_mock_webhook(
        ac,
        {
            "event": "charge.success",
            "data": {
                "id": 9000,
                "reference": reference,
                "status": "success",
                "authorization": {"authorization_code": "AUTH_omitted01", "reusable": True},
            },
        },
    )
    assert omitted_auth.json()["data"]["outcome"] == "mismatch"
    omitted_profile = (await ac.get("/api/v1/billing/account", headers=headers)).json()["data"]
    assert omitted_profile["authorization_present"] is False
    withheld = await _post_mock_webhook(
        ac,
        {
            "event": "charge.success",
            "data": {
                "id": 9001,
                "reference": reference,
                "amount": amount_minor,
                "currency": currency,
                "status": "success",
                "tenant_id": seed["t1"].id,
                "authorization": {"authorization_code": "AUTH_not_reusable", "reusable": False},
            },
        },
    )
    assert withheld.json()["data"]["outcome"] == "ignored"
    still = (await ac.get("/api/v1/billing/account", headers=headers)).json()["data"]
    assert still["authorization_present"] is False
    token = "AUTH_confirmed01"
    confirmed = await _post_mock_webhook(
        ac,
        {
            "event": "charge.success",
            "data": {
                "id": 9002,
                "reference": reference,
                "amount": amount_minor,
                "currency": currency,
                "status": "success",
                "tenant_id": seed["t1"].id,
                "authorization": {"authorization_code": token, "reusable": True},
                "customer": {"customer_code": "CUS_localtest"},
            },
        },
    )
    assert confirmed.json()["data"]["outcome"] == "authorization_saved"
    assert confirmed.json()["data"]["duplicate"] is False
    saved = await ac.get("/api/v1/billing/account", headers=headers)
    assert token not in saved.text
    assert saved.json()["data"]["authorization_present"] is True
    returned = await ac.get(
        f"/api/v1/billing/checkout/return?trxref={reference}&reference={reference}",
        headers=headers,
    )
    assert returned.status_code == 200, returned.text
    returned_body = returned.json()["data"]
    assert returned_body["confirmed_by_redirect"] is False
    assert returned_body["paid"] is False
    assert returned_body["authorization_present"] is True
    again = (await ac.get("/api/v1/billing/invoices", headers=headers)).json()["data"]
    assert all(row["status"] != "paid" for row in again)
    assert await _invoice_count(seed["t1"].id) == before

    def _refuse_network(*_args, **_kwargs):
        raise AssertionError("unconfigured checkout must not call the provider")

    monkeypatch.setattr(settings, "BILLING_PROVIDER", "paystack")
    monkeypatch.setattr(settings, "PAYSTACK_SECRET_KEY", "")
    monkeypatch.setattr("httpx.post", _refuse_network)
    unavailable = await ac.post(
        "/api/v1/billing/checkout",
        json={"plan_code": "professional-month"},
        headers=headers,
    )
    assert unavailable.status_code == 503, unavailable.text
    assert "not configured" in unavailable.text.lower()
    assert '"paid":true' not in unavailable.text.replace(" ", "").lower()
