"""ADR-002 paid billing scaffold — Complete still MISSING."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

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
    assert billing_svc.PAID_BILLING_COMPLETE_CLAIMED is False


@pytest.mark.asyncio
async def test_billing_status_and_portal_skeleton_not_configured(client, db_session):
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
    assert "payment_success" not in body or body.get("payment_success") is not True

    portal = await ac.post(
        "/api/v1/billing/portal-session",
        headers=headers,
        json={"return_url": "https://example.test/company"},
    )
    assert portal.status_code == 200, portal.text
    pdata = portal.json()["data"]
    assert pdata["status"] == "not_configured"
    assert pdata["portal_url"] is None
    assert pdata["payment_success"] is False
    assert pdata["payment_processed"] is False
    assert pdata["paid_billing_complete_claimed"] is False
    assert pdata["customer"]["tenant_id"] == seed["t1"].id

    # Local customer row created; no provider customer id invented as live.
    row = (
        await db_session.execute(
            select(m.TenantBillingCustomer).where(
                m.TenantBillingCustomer.tenant_id == seed["t1"].id
            )
        )
    ).scalar_one()
    assert row.provider_customer_id is None
    assert (row.metadata_json or {}).get("live_customer_create_deferred") is True


@pytest.mark.asyncio
async def test_portal_skeleton_keys_present_still_deferred(client, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    monkeypatch.setattr(settings, "BILLING_PROVIDER", "stripe")
    monkeypatch.setattr(settings, "BILLING_PROVIDER_SECRET_KEY", "sk_test_scaffold")
    monkeypatch.setattr("app.billing_provider.settings.BILLING_PROVIDER", "stripe")
    monkeypatch.setattr(
        "app.billing_provider.settings.BILLING_PROVIDER_SECRET_KEY", "sk_test_scaffold"
    )

    portal = await ac.post("/api/v1/billing/portal-session", headers=headers, json={})
    assert portal.status_code == 200, portal.text
    pdata = portal.json()["data"]
    assert pdata["status"] == "provider_keys_present_live_call_deferred"
    assert pdata["portal_url"] is None
    assert pdata["provider_keys_present"] is True
    assert pdata["payment_success"] is False
    assert pdata["checkout_enabled"] is False


@pytest.mark.asyncio
async def test_webhook_mirrors_subscription_without_payment_success(client, db_session):
    ac, seed = client
    tid = seed["t1"].id
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

    # Tenant plan_code must not be mutated by webhook stub
    await db_session.refresh(seed["t1"])
    tenant = await db_session.get(m.Tenant, tid)
    assert tenant.plan_code == seed["t1"].plan_code


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature_when_secret_set(client, monkeypatch):
    ac, seed = client
    monkeypatch.setattr(settings, "BILLING_PROVIDER_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(
        "app.billing_provider.settings.BILLING_PROVIDER_WEBHOOK_SECRET", "whsec_test"
    )
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

    ts = str(int(time.time()))
    signed = f"{ts}.".encode("utf-8") + body
    sig = hmac.new(b"whsec_test", signed, hashlib.sha256).hexdigest()
    ok = await ac.post(
        "/api/v1/billing/webhooks/provider",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": f"t={ts},v1={sig}",
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

    monkeypatch.setattr(settings, "PAID_BILLING_ENTITLEMENT_GATE_ENABLED", True)
    monkeypatch.setattr(
        "app.billing_provider.settings.PAID_BILLING_ENTITLEMENT_GATE_ENABLED", True
    )
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
