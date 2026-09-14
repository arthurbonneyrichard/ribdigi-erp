"""ADR-002 paid billing PARTIAL — portal session + webhook proof (Complete MISSING)."""

from __future__ import annotations

import hashlib
import hmac
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
    assert body["provider_mode"] == "unconfigured"

    portal = await ac.post(
        "/api/v1/billing/portal-session",
        headers=headers,
        json={"return_url": "https://example.test/company"},
    )
    assert portal.status_code == 503, portal.text
    detail = portal.json()["detail"]
    assert "not configured" in str(detail).lower() or "BILLING_PROVIDER" in str(detail)


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
    assert data["processing_status"] == "recorded"
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
    assert row.processing_status == "recorded"

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
async def test_entitlement_gate_flag_default_off_and_armed_non_authoritative(
    client, monkeypatch
):
    ac, seed = client
    headers = await _super(ac, seed)
    status = await ac.get("/api/v1/billing/status", headers=headers)
    assert status.json()["data"]["paid_billing_entitlement_gate_enabled"] is False
    assert status.json()["data"]["operational_gate"] == "trial_grace_suspend_lifecycle"

    _patch_billing(monkeypatch, PAID_BILLING_ENTITLEMENT_GATE_ENABLED=True)
    status2 = await ac.get("/api/v1/billing/status", headers=headers)
    body = status2.json()["data"]
    assert body["paid_billing_entitlement_gate_enabled"] is True
    assert "legacy_trial_still_authoritative" in body["operational_gate"]
    assert body["paid_billing_complete_claimed"] is False


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


def test_company_ui_opens_portal_url_when_present():
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "/billing/portal-session" in page
    assert "portal_url" in page
    assert "window.location.assign(data.portal_url)" in page
    assert "paid billing Complete" in page.lower() or "Complete remains MISSING" in page
