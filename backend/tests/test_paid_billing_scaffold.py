"""ADR-002 paid billing PARTIAL — portal/checkout session + webhook proof (Complete MISSING)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import httpx
import pyotp
import pytest
from sqlalchemy import func, select

from app import billing_provider as billing_svc
from app import models as m
from app.config import settings
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _patch_billing(monkeypatch, **kwargs):
    for key, value in kwargs.items():
        monkeypatch.setattr(settings, key, value)
        monkeypatch.setattr(f"app.billing_provider.settings.{key}", value)


def test_scaffold_docs_and_honesty_constants():
    assert (ROOT / "docs/ADR_002_PAID_BILLING_SCAFFOLD.md").is_file()
    assert (ROOT / "docs/PAID_BILLING_PROVIDER_OPS.md").is_file()
    assert (ROOT / "backend/alembic/versions/20260914_0114_paid_billing_scaffold.py").is_file()
    honesty = billing_svc.honesty_payload()
    assert honesty["paid_billing_complete_claimed"] is False
    assert honesty["checkout_success_claimed"] is False
    assert honesty["payment_provider_live_claimed"] is False
    assert honesty["subscriptions_live_claimed"] is False
    assert honesty["mrr_fabricated_claimed"] is False
    assert honesty["billing_deferred"] is True
    assert honesty["checkout_enabled"] is False
    assert honesty["scaffold_status"] == "partial"
    assert honesty["engineering_mock_soak_ready"] is True
    assert honesty["paid_billing_complete_ops_blocked"] is True
    assert honesty["paid_billing_complete_blocker"] == "live_stripe_keys_and_staging_soak"
    assert honesty["paid_billing_entitlement_gate_enabled"] is False
    assert honesty["provider_mode"] == "unconfigured"
    assert billing_svc.PAID_BILLING_COMPLETE_CLAIMED is False


@pytest.mark.asyncio
async def test_billing_status_and_portal_unconfigured_fails_clearly(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    status = await ac.get("/api/v1/billing/status", headers=headers)
    assert status.status_code == 200, status.text
    body = status.json()["data"]
    assert body["paid_billing_complete_claimed"] is False
    assert body["billing_deferred"] is True
    assert body["billing_provider"] is None
    assert body["checkout_enabled"] is False
    assert body["portal"]["available"] is False
    assert body["portal"]["reason"] == "not_configured"
    assert body["checkout"]["available"] is False
    assert body["checkout"]["reason"] == "not_configured"
    assert body["checkout"]["auto_plan_upgrade"] is False
    assert body["provider_mode"] == "unconfigured"

    portal = await ac.post(
        "/api/v1/billing/portal-session",
        headers=headers,
        json={"return_url": "https://example.test/company"},
    )
    assert portal.status_code == 503, portal.text
    detail = portal.json()["detail"]
    assert "not configured" in str(detail).lower() or "BILLING_PROVIDER" in str(detail)

    checkout = await ac.post(
        "/api/v1/billing/checkout-session",
        headers=headers,
        json={
            "success_url": "https://example.test/company?ok=1",
            "cancel_url": "https://example.test/company?cancel=1",
            "plan_code": "starter",
        },
    )
    assert checkout.status_code == 503, checkout.text
    cdetail = checkout.json()["detail"]
    assert "not configured" in str(cdetail).lower() or "BILLING_PROVIDER" in str(cdetail)


@pytest.mark.asyncio
async def test_portal_mock_mode_returns_portal_url(client, db_session, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    _patch_billing(
        monkeypatch,
        BILLING_PROVIDER="stripe",
        BILLING_PROVIDER_SECRET_KEY="sk_test_mock_ci",
        BILLING_PROVIDER_MODE="mock",
        BILLING_PROVIDER_PORTAL_RETURN_URL="https://example.test/company",
    )

    status = await ac.get("/api/v1/billing/status", headers=headers)
    assert status.status_code == 200, status.text
    sbody = status.json()["data"]
    assert sbody["provider_mode"] == "mock"
    assert sbody["portal"]["available"] is True
    assert sbody["portal"]["reason"] == "mock_portal_session_ready"
    assert sbody["checkout"]["available"] is True
    assert sbody["checkout"]["reason"] == "mock_checkout_session_ready"
    assert sbody["paid_billing_complete_claimed"] is False

    portal = await ac.post(
        "/api/v1/billing/portal-session",
        headers=headers,
        json={"return_url": "https://example.test/company"},
    )
    assert portal.status_code == 200, portal.text
    pdata = portal.json()["data"]
    assert pdata["status"] == "mock_portal_session_created"
    assert pdata["portal_url"]
    assert pdata["portal_url"].startswith("https://billing.stripe.test/mock/session")
    assert pdata["payment_success"] is False
    assert pdata["payment_processed"] is False
    assert pdata["paid_billing_complete_claimed"] is False
    assert pdata["checkout_enabled"] is False
    assert pdata["customer"]["provider_customer_id"].startswith("cus_mock_")

    row = (
        await db_session.execute(
            select(m.TenantBillingCustomer).where(
                m.TenantBillingCustomer.tenant_id == seed["t1"].id
            )
        )
    ).scalar_one()
    assert row.provider_customer_id.startswith("cus_mock_")
    assert (row.metadata_json or {}).get("mock_portal") is True


@pytest.mark.asyncio
async def test_checkout_mock_mode_returns_checkout_url(client, db_session, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    plan_before = seed["t1"].plan_code
    _patch_billing(
        monkeypatch,
        BILLING_PROVIDER="stripe",
        BILLING_PROVIDER_SECRET_KEY="sk_test_mock_ci",
        BILLING_PROVIDER_MODE="mock",
        BILLING_PROVIDER_CHECKOUT_SUCCESS_URL="https://example.test/company?ok=1",
        BILLING_PROVIDER_CHECKOUT_CANCEL_URL="https://example.test/company?cancel=1",
    )

    checkout = await ac.post(
        "/api/v1/billing/checkout-session",
        headers=headers,
        json={
            "success_url": "https://example.test/company?ok=1",
            "cancel_url": "https://example.test/company?cancel=1",
            "plan_code": "starter",
        },
    )
    assert checkout.status_code == 200, checkout.text
    data = checkout.json()["data"]
    assert data["status"] == "mock_checkout_session_created"
    assert data["checkout_url"]
    assert data["checkout_url"].startswith("https://checkout.stripe.test/mock/session")
    assert data["payment_success"] is False
    assert data["payment_processed"] is False
    assert data["auto_plan_upgrade"] is False
    assert data["tenant_plan_code_unchanged"] is True
    assert data["paid_billing_complete_claimed"] is False
    assert data["checkout_success_claimed"] is False
    assert data["checkout_enabled"] is False
    assert data["plan_code"] == "starter"
    assert data["customer"]["provider_customer_id"].startswith("cus_mock_")

    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    assert tenant.plan_code == plan_before

    row = (
        await db_session.execute(
            select(m.TenantBillingCustomer).where(
                m.TenantBillingCustomer.tenant_id == seed["t1"].id
            )
        )
    ).scalar_one()
    assert (row.metadata_json or {}).get("mock_checkout") is True


@pytest.mark.asyncio
async def test_portal_live_mode_with_httpx_mock(client, db_session, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    _patch_billing(
        monkeypatch,
        BILLING_PROVIDER="stripe",
        BILLING_PROVIDER_SECRET_KEY="sk_test_live_path",
        BILLING_PROVIDER_MODE="live",
        BILLING_PROVIDER_API_BASE="https://api.stripe.test",
    )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url.path))
        if request.url.path.endswith("/v1/customers"):
            return httpx.Response(200, json={"id": "cus_live_test_1", "object": "customer"})
        if request.url.path.endswith("/v1/billing_portal/sessions"):
            return httpx.Response(
                200,
                json={
                    "id": "bps_live_test_1",
                    "object": "billing_portal.session",
                    "url": "https://billing.stripe.com/session/test_live_portal",
                },
            )
        return httpx.Response(404, json={"error": {"message": "not found"}})

    transport = httpx.MockTransport(handler)
    with patch.object(billing_svc, "_http_transport", transport):
        portal = await ac.post(
            "/api/v1/billing/portal-session",
            headers=headers,
            json={"return_url": "https://example.test/company"},
        )
    assert portal.status_code == 200, portal.text
    pdata = portal.json()["data"]
    assert pdata["status"] == "live_portal_session_created"
    assert pdata["portal_url"] == "https://billing.stripe.com/session/test_live_portal"
    assert pdata["portal_session_id"] == "bps_live_test_1"
    assert pdata["payment_success"] is False
    assert pdata["paid_billing_complete_claimed"] is False
    assert "/v1/customers" in calls[0] or any(c.endswith("/v1/customers") for c in calls)
    assert any(c.endswith("/v1/billing_portal/sessions") for c in calls)

    row = (
        await db_session.execute(
            select(m.TenantBillingCustomer).where(
                m.TenantBillingCustomer.tenant_id == seed["t1"].id
            )
        )
    ).scalar_one()
    assert row.provider_customer_id == "cus_live_test_1"


@pytest.mark.asyncio
async def test_checkout_live_mode_with_httpx_mock(client, db_session, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    plan_before = seed["t1"].plan_code
    _patch_billing(
        monkeypatch,
        BILLING_PROVIDER="stripe",
        BILLING_PROVIDER_SECRET_KEY="sk_test_live_path",
        BILLING_PROVIDER_MODE="live",
        BILLING_PROVIDER_API_BASE="https://api.stripe.test",
        BILLING_PROVIDER_PRICE_IDS=json.dumps({"starter": "price_live_starter"}),
    )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url.path))
        if request.url.path.endswith("/v1/customers"):
            return httpx.Response(200, json={"id": "cus_live_checkout_1", "object": "customer"})
        if request.url.path.endswith("/v1/checkout/sessions"):
            return httpx.Response(
                200,
                json={
                    "id": "cs_live_test_1",
                    "object": "checkout.session",
                    "url": "https://checkout.stripe.com/c/pay/test_live_checkout",
                },
            )
        return httpx.Response(404, json={"error": {"message": "not found"}})

    with patch.object(billing_svc, "_http_transport", httpx.MockTransport(handler)):
        checkout = await ac.post(
            "/api/v1/billing/checkout-session",
            headers=headers,
            json={
                "success_url": "https://example.test/company?ok=1",
                "cancel_url": "https://example.test/company?cancel=1",
                "plan_code": "starter",
            },
        )
    assert checkout.status_code == 200, checkout.text
    data = checkout.json()["data"]
    assert data["status"] == "live_checkout_session_created"
    assert data["checkout_url"] == "https://checkout.stripe.com/c/pay/test_live_checkout"
    assert data["checkout_session_id"] == "cs_live_test_1"
    assert data["payment_success"] is False
    assert data["auto_plan_upgrade"] is False
    assert data["paid_billing_complete_claimed"] is False
    assert any(c.endswith("/v1/checkout/sessions") for c in calls)

    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    assert tenant.plan_code == plan_before


@pytest.mark.asyncio
async def test_portal_live_provider_failure_no_fake_success(client, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    _patch_billing(
        monkeypatch,
        BILLING_PROVIDER="stripe",
        BILLING_PROVIDER_SECRET_KEY="sk_test_live_path",
        BILLING_PROVIDER_MODE="live",
        BILLING_PROVIDER_API_BASE="https://api.stripe.test",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API Key"}})

    with patch.object(billing_svc, "_http_transport", httpx.MockTransport(handler)):
        portal = await ac.post(
            "/api/v1/billing/portal-session",
            headers=headers,
            json={"return_url": "https://example.test/company"},
        )
    assert portal.status_code == 502, portal.text
    assert "payment_success" not in portal.text.lower() or "false" in portal.text.lower()


@pytest.mark.asyncio
async def test_checkout_live_missing_price_fails_clearly(client, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    _patch_billing(
        monkeypatch,
        BILLING_PROVIDER="stripe",
        BILLING_PROVIDER_SECRET_KEY="sk_test_live_path",
        BILLING_PROVIDER_MODE="live",
        BILLING_PROVIDER_API_BASE="https://api.stripe.test",
        BILLING_PROVIDER_PRICE_IDS="",
    )
    checkout = await ac.post(
        "/api/v1/billing/checkout-session",
        headers=headers,
        json={
            "success_url": "https://example.test/company?ok=1",
            "cancel_url": "https://example.test/company?cancel=1",
            "plan_code": "starter",
        },
    )
    assert checkout.status_code == 400, checkout.text
    assert "price_id" in str(checkout.json()["detail"]).lower()


@pytest.mark.asyncio
async def test_webhook_mirrors_subscription_without_payment_success(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
    plan_before = seed["t1"].plan_code
    payload = {
        "id": "evt_scaffold_sub_1",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_scaffold_1",
                "status": "active",
                "cancel_at_period_end": False,
                "current_period_end": int(time.time()) + 86400,
                "metadata": {"tenant_id": tid, "plan_code": "growth"},
                "items": {"data": []},
            }
        },
    }
    body = json.dumps(payload).encode("utf-8")
    resp = await ac.post(
        "/api/v1/billing/webhooks/provider",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["payment_success"] is False
    assert data["payment_processed"] is False
    assert data["paid_billing_complete_claimed"] is False
    assert data["entitlement_gate_applied"] is False
    assert data["processing_status"] == "mirrored"
    assert data["duplicate"] is False

    # Idempotent replay
    resp2 = await ac.post(
        "/api/v1/billing/webhooks/provider",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["data"]["duplicate"] is True

    sub = (
        await db_session.execute(
            select(m.TenantBillingSubscription).where(
                m.TenantBillingSubscription.provider_subscription_id == "sub_scaffold_1"
            )
        )
    ).scalar_one()
    assert sub.tenant_id == tid
    assert sub.status == "active"
    assert sub.plan_code == "growth"
    assert (sub.metadata_json or {}).get("payment_success") is False

    # Tenant plan_code must not be mutated by webhook
    tenant = await db_session.get(m.Tenant, tid)
    assert tenant.plan_code == plan_before


@pytest.mark.asyncio
async def test_signed_webhook_proof_valid_invalid_idempotent(client, db_session, monkeypatch):
    """Signed webhook proof: valid sig / invalid sig / idempotent event store."""
    ac, seed = client
    secret = "whsec_proof_test"
    _patch_billing(monkeypatch, BILLING_PROVIDER_WEBHOOK_SECRET=secret)

    payload = {
        "id": "evt_signed_proof_1",
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": "in_proof_1",
                "status": "paid",
                "metadata": {"tenant_id": seed["t1"].id},
            }
        },
    }
    body = json.dumps(payload).encode("utf-8")
    plan_before = seed["t1"].plan_code

    # Invalid signature → 400, no event row
    bad = await ac.post(
        "/api/v1/billing/webhooks/provider",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=1,v1=deadbeef",
        },
    )
    assert bad.status_code == 400, bad.text
    count_after_bad = (
        await db_session.execute(
            select(func.count()).select_from(m.BillingWebhookEvent).where(
                m.BillingWebhookEvent.provider_event_id == "evt_signed_proof_1"
            )
        )
    ).scalar_one()
    assert count_after_bad == 0

    # Valid signature → stored with signature_valid
    header = billing_svc.sign_provider_webhook_header(body=body, secret=secret)
    ok = await ac.post(
        "/api/v1/billing/webhooks/provider",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": header,
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["signature_valid"] is True
    assert data["duplicate"] is False
    assert data["payment_success"] is False
    assert data["processing_status"] in ("recorded", "recorded_invoice_paid_no_complete")
    assert data["paid_billing_complete_claimed"] is False

    row = (
        await db_session.execute(
            select(m.BillingWebhookEvent).where(
                m.BillingWebhookEvent.provider_event_id == "evt_signed_proof_1"
            )
        )
    ).scalar_one()
    assert row.signature_valid is True
    assert row.event_type == "invoice.paid"
    assert row.processing_status in ("recorded", "recorded_invoice_paid_no_complete")

    # Idempotent replay with same valid signature
    ok2 = await ac.post(
        "/api/v1/billing/webhooks/provider",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": header,
        },
    )
    assert ok2.status_code == 200, ok2.text
    assert ok2.json()["data"]["duplicate"] is True
    assert ok2.json()["data"]["payment_success"] is False

    count_final = (
        await db_session.execute(
            select(func.count()).select_from(m.BillingWebhookEvent).where(
                m.BillingWebhookEvent.provider_event_id == "evt_signed_proof_1"
            )
        )
    ).scalar_one()
    assert count_final == 1

    # invoice.paid must NOT mutate Tenant.plan_code / claim Complete
    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    assert tenant.plan_code == plan_before


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature_when_secret_set(client, monkeypatch):
    ac, seed = client
    _patch_billing(monkeypatch, BILLING_PROVIDER_WEBHOOK_SECRET="whsec_test")
    payload = {"id": "evt_bad_sig", "type": "ping", "data": {"object": {}}}
    body = json.dumps(payload).encode("utf-8")
    bad = await ac.post(
        "/api/v1/billing/webhooks/provider",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=1,v1=deadbeef",
        },
    )
    assert bad.status_code == 400, bad.text

    header = billing_svc.sign_provider_webhook_header(body=body, secret="whsec_test")
    ok = await ac.post(
        "/api/v1/billing/webhooks/provider",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": header,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["signature_valid"] is True
    assert ok.json()["data"]["payment_success"] is False


@pytest.mark.asyncio
async def test_entitlement_gate_flag_default_off_and_on_operational_gate(
    client, monkeypatch
):
    ac, seed = client
    headers = await _super(ac, seed)
    status = await ac.get("/api/v1/billing/status", headers=headers)
    body = status.json()["data"]
    assert body["paid_billing_entitlement_gate_enabled"] is False
    assert body["operational_gate"] == "trial_grace_suspend_lifecycle"
    assert body["entitlement_gated_routes"] == [
        "POST /api/v1/sales",
        "PATCH /api/v1/companies/{company_id}",
    ]
    assert body["entitlement_gate"]["enabled"] is False
    assert body["entitlement_gate"]["applied_to_routes"] == []
    assert body["entitlement_gate"]["legacy_trial_authoritative_when_off"] is True

    _patch_billing(monkeypatch, PAID_BILLING_ENTITLEMENT_GATE_ENABLED=True)
    status2 = await ac.get("/api/v1/billing/status", headers=headers)
    body2 = status2.json()["data"]
    assert body2["paid_billing_entitlement_gate_enabled"] is True
    assert (
        body2["operational_gate"]
        == "provider_subscription_mirror_authoritative_for_gated_routes"
    )
    assert body2["entitlement_gate"]["enabled"] is True
    assert body2["entitlement_gate"]["applied_to_routes"] == [
        "POST /api/v1/sales",
        "PATCH /api/v1/companies/{company_id}",
    ]
    assert body2["paid_billing_complete_claimed"] is False
    assert body2["checkout_enabled"] is False


async def _seed_subscription(db_session, *, tenant_id: str, status: str):
    customer = await billing_svc.ensure_billing_customer(
        db_session, tenant_id=tenant_id, email="billing@alpha.example.com"
    )
    row = m.TenantBillingSubscription(
        tenant_id=tenant_id,
        billing_customer_id=customer.id,
        provider="stripe",
        provider_subscription_id=f"sub_test_{status}_{tenant_id[:8]}",
        status=status,
        raw_status=status,
        metadata_json={"scaffold_mirror": True, "payment_success": False},
    )
    db_session.add(row)
    await db_session.commit()
    return row


def _company_headers(headers, seed):
    out = dict(headers)
    out["X-Workspace-Kind"] = "company"
    out["X-Company-ID"] = seed["c1"].id
    return out


@pytest.mark.asyncio
async def test_entitlement_gate_off_legacy_allows_sale_and_company_patch_without_sub(
    client, db_session, monkeypatch
):
    """Flag OFF: gated routes behave as today (trial lifecycle), no subscription needed."""
    ac, seed = client
    headers = await _super(ac, seed)
    _patch_billing(monkeypatch, PAID_BILLING_ENTITLEMENT_GATE_ENABLED=False)

    sale = await ac.post(
        "/api/v1/sales",
        headers=_company_headers(headers, seed),
        json={
            "party_id": seed["party1"].id,
            "subtotal": 5,
            "tax": 0,
            "total": 5,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text

    patch = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}",
        headers=headers,
        json={"name": "Alpha Co Gate Off"},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["data"]["name"] == "Alpha Co Gate Off"


@pytest.mark.asyncio
async def test_entitlement_gate_on_active_allows_gated_routes(
    client, db_session, monkeypatch
):
    ac, seed = client
    headers = await _super(ac, seed)
    _patch_billing(monkeypatch, PAID_BILLING_ENTITLEMENT_GATE_ENABLED=True)
    await _seed_subscription(db_session, tenant_id=seed["t1"].id, status="active")

    sale = await ac.post(
        "/api/v1/sales",
        headers=_company_headers(headers, seed),
        json={
            "party_id": seed["party1"].id,
            "subtotal": 6,
            "tax": 0,
            "total": 6,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 200, sale.text

    patch = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}",
        headers=headers,
        json={"name": "Alpha Co Active Sub"},
    )
    assert patch.status_code == 200, patch.text


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_status", ["past_due", "canceled", "cancelled"])
async def test_entitlement_gate_on_deny_statuses_block_gated_routes(
    client, db_session, monkeypatch, bad_status
):
    ac, seed = client
    headers = await _super(ac, seed)
    _patch_billing(monkeypatch, PAID_BILLING_ENTITLEMENT_GATE_ENABLED=True)
    await _seed_subscription(db_session, tenant_id=seed["t1"].id, status=bad_status)

    sale = await ac.post(
        "/api/v1/sales",
        headers=_company_headers(headers, seed),
        json={
            "party_id": seed["party1"].id,
            "subtotal": 7,
            "tax": 0,
            "total": 7,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 403, sale.text
    detail = sale.json()["detail"]
    assert detail["code"] == "PAID_BILLING_ENTITLEMENT_DENIED"
    assert detail["deny_reason"] == "subscription_status_denied"
    assert detail["paid_billing_complete_claimed"] is False
    assert detail["payment_success"] is False

    patch = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}",
        headers=headers,
        json={"name": f"Blocked {bad_status}"},
    )
    assert patch.status_code == 403, patch.text
    assert patch.json()["detail"]["code"] == "PAID_BILLING_ENTITLEMENT_DENIED"


@pytest.mark.asyncio
async def test_entitlement_gate_on_missing_subscription_denies(
    client, db_session, monkeypatch
):
    ac, seed = client
    headers = await _super(ac, seed)
    _patch_billing(monkeypatch, PAID_BILLING_ENTITLEMENT_GATE_ENABLED=True)
    # No subscription row seeded.

    sale = await ac.post(
        "/api/v1/sales",
        headers=_company_headers(headers, seed),
        json={
            "party_id": seed["party1"].id,
            "subtotal": 4,
            "tax": 0,
            "total": 4,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 403, sale.text
    detail = sale.json()["detail"]
    assert detail["code"] == "PAID_BILLING_ENTITLEMENT_DENIED"
    assert detail["deny_reason"] == "subscription_missing"
    assert detail["subscription_status"] is None

    patch = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}",
        headers=headers,
        json={"name": "Blocked Missing"},
    )
    assert patch.status_code == 403, patch.text


def test_subscription_status_allows_access_unit():
    assert billing_svc.subscription_status_allows_access("active") is True
    assert billing_svc.subscription_status_allows_access("trialing") is True
    assert billing_svc.subscription_status_allows_access("past_due") is False
    assert billing_svc.subscription_status_allows_access("canceled") is False
    assert billing_svc.subscription_status_allows_access(None) is False
    assert billing_svc.subscription_status_allows_access("") is False


@pytest.mark.asyncio
async def test_store_manager_denied_billing_status(client):
    ac, seed = client
    mgr_headers = await auth_headers(
        ac, email="mgr@alpha.example.com", tenant_slug="alpha"
    )
    denied = await ac.get("/api/v1/billing/status", headers=mgr_headers)
    assert denied.status_code == 403, denied.text


def test_platform_billing_honesty_payload_shape():
    """Unit-level: platform billing merges scaffold honesty (no live Complete)."""
    honesty = billing_svc.honesty_payload()
    assert honesty["scaffold_status"] == "partial"
    assert honesty["paid_billing_complete_claimed"] is False
    assert honesty["checkout_enabled"] is False
    assert honesty["mrr_fabricated_claimed"] is False
    assert honesty["entitlement_gated_routes"] == list(billing_svc.GATED_ROUTE_ALLOWLIST)


def test_company_ui_opens_portal_and_checkout_urls_when_present():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "/billing/portal-session" in page
    assert "portal_url" in page
    assert "window.location.assign(data.portal_url)" in page
    assert "/billing/checkout-session" in page
    assert "checkout_url" in page
    assert "window.location.assign(data.checkout_url)" in page
    assert "paid billing Complete" in page.lower() or "Complete remains MISSING" in page
    assert "auto-upgrade" in page.lower() or "does not auto-upgrade" in page.lower()


def test_entitlement_gate_prod_example_defaults_off_and_go_live_pack_present():
    """Ops readiness: prod template stays fail-closed; operator go-live pack exists."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "PAID_BILLING_ENTITLEMENT_GATE_ENABLED=false" in example
    assert "BILLING_PROVIDER=" in example
    assert "BILLING_CHECKOUT_ENABLED=false" in example

    prod = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "PAID_BILLING_ENTITLEMENT_GATE_ENABLED=false" in prod
    assert "BILLING_PROVIDER=" in prod
    assert "BILLING_PROVIDER_SECRET_KEY=" in prod
    assert "BILLING_PROVIDER_WEBHOOK_SECRET=" in prod
    assert "BILLING_CHECKOUT_ENABLED=false" in prod
    # Must not flip production template ON from engineering soak alone.
    assert "PAID_BILLING_ENTITLEMENT_GATE_ENABLED=true" not in prod

    pack = (ROOT / "docs/GO_LIVE_READINESS_CHECKLIST.md").read_text(encoding="utf-8")
    assert "PAID_BILLING_ENTITLEMENT_GATE_ENABLED" in pack
    assert "STORE_MEMBERSHIP_SCOPE_ENABLED" in pack
    assert "OFFLINE_PUSH_ENABLED" in pack
    assert "offline_wipe_push_staging_checklist.md" in pack
    assert "adr005_staging_soak_checklist.md" in pack
    assert "OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md" in pack
    assert "PAID_BILLING_PROVIDER_OPS.md" in pack
    assert "paid_billing_staging_soak_checklist.md" in pack
    cl = pack.lower()
    for forbidden_complete in (
        "offline complete",
        "7-day",
        "go-live",
        "paid billing complete",
        "adr-005 complete",
        "store-scoped rbac complete",
    ):
        assert forbidden_complete in cl
    assert "missing" in cl
    assert "partial" in cl
    # Must not claim Completes from the pack alone
    assert "do not claim" in cl or "do **not** claim" in pack.lower() or "not claim" in cl
