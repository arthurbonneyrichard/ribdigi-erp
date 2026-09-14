"""ADR-002 Phase E — automated mock-provider soak (engineering ready; Complete MISSING).

Proves end-to-end with ``BILLING_PROVIDER_MODE=mock`` + gate ON:

- Portal + Checkout Session create (mock URLs; never payment_success)
- Signed webhook lifecycle: created → active → past_due → canceled
- ``checkout.session.completed`` + ``invoice.paid`` recorded without plan_code
  mutation / payment_success Complete claims
- Entitlement gate allowlist allow/deny on gated routes
- Prod defaults stay OFF (ops enable is cutover; live Stripe still required)

Paid billing Complete remains **MISSING** — ops-blocked on live Stripe keys +
staging soak (``docs/paid_billing_staging_soak_checklist.md``). Analogous to
SEC-M2 Phase E: automated evidence closes the engineering path; production
enable / live provider is a separate ops step, not a fake Complete.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from sqlalchemy import select

from app import billing_provider as billing_svc
from app import models as m
from app.config import Settings, settings
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    import pyotp

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _patch_billing(monkeypatch, **kwargs):
    for key, value in kwargs.items():
        monkeypatch.setattr(settings, key, value)
        monkeypatch.setattr(f"app.billing_provider.settings.{key}", value)


def _company_headers(headers, seed):
    out = dict(headers)
    out["X-Workspace-Kind"] = "company"
    out["X-Company-ID"] = seed["c1"].id
    return out


def _enable_mock_provider(monkeypatch, *, gate: bool = True):
    _patch_billing(
        monkeypatch,
        BILLING_PROVIDER="stripe",
        BILLING_PROVIDER_SECRET_KEY="sk_test_mock_soak",
        BILLING_PROVIDER_MODE="mock",
        BILLING_PROVIDER_WEBHOOK_SECRET="whsec_test_soak",
        BILLING_PROVIDER_PORTAL_RETURN_URL="https://example.test/company",
        BILLING_PROVIDER_CHECKOUT_SUCCESS_URL="https://example.test/company?ok=1",
        BILLING_PROVIDER_CHECKOUT_CANCEL_URL="https://example.test/company?cancel=1",
        BILLING_PROVIDER_PRICE_IDS=json.dumps({"starter": "price_mock_starter"}),
        PAID_BILLING_ENTITLEMENT_GATE_ENABLED=gate,
        BILLING_CHECKOUT_ENABLED=False,
    )


def _sign(body: bytes) -> str:
    return billing_svc.sign_provider_webhook_header(
        body=body, secret="whsec_test_soak", timestamp=int(time.time())
    )


async def _post_webhook(ac, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    return await ac.post(
        "/api/v1/billing/webhooks/provider",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": _sign(body),
        },
    )


def test_soak_flag_and_complete_still_default_off_ops_blocked():
    """Engineering soak does not flip Complete or prod gate default."""
    cfg = Settings(APP_ENV="development")
    assert cfg.PAID_BILLING_ENTITLEMENT_GATE_ENABLED is False
    assert cfg.BILLING_CHECKOUT_ENABLED is False
    honesty = billing_svc.honesty_payload()
    assert honesty["paid_billing_complete_claimed"] is False
    assert honesty["checkout_success_claimed"] is False
    assert honesty["payment_provider_live_claimed"] is False
    assert honesty["subscriptions_live_claimed"] is False
    assert honesty["mrr_fabricated_claimed"] is False
    assert honesty["engineering_mock_soak_ready"] is True
    assert honesty["paid_billing_complete_ops_blocked"] is True
    assert honesty["paid_billing_complete_blocker"] == "live_stripe_keys_and_staging_soak"
    assert billing_svc.PAID_BILLING_COMPLETE_CLAIMED is False

    prod = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    assert "PAID_BILLING_ENTITLEMENT_GATE_ENABLED=false" in prod
    assert "BILLING_CHECKOUT_ENABLED=false" in prod
    assert (ROOT / "docs/paid_billing_staging_soak_checklist.md").is_file()
    assert (ROOT / "docs/PAID_BILLING_PROVIDER_OPS.md").is_file()
    assert (ROOT / "docs/ADR_002_PAID_BILLING_SCAFFOLD.md").is_file()


async def test_soak_portal_checkout_mock_and_status(client, monkeypatch):
    ac, seed = client
    headers = await _super(ac, seed)
    _enable_mock_provider(monkeypatch, gate=True)

    status = await ac.get("/api/v1/billing/status", headers=headers)
    assert status.status_code == 200, status.text
    body = status.json()["data"]
    assert body["provider_mode"] == "mock"
    assert body["portal"]["available"] is True
    assert body["checkout"]["available"] is True
    assert body["checkout"]["auto_plan_upgrade"] is False
    assert body["paid_billing_complete_claimed"] is False
    assert body["checkout_enabled"] is False
    assert body["paid_billing_entitlement_gate_enabled"] is True
    assert body["engineering_mock_soak_ready"] is True
    assert body["paid_billing_complete_ops_blocked"] is True

    portal = await ac.post(
        "/api/v1/billing/portal-session",
        headers=headers,
        json={"return_url": "https://example.test/company"},
    )
    assert portal.status_code == 200, portal.text
    pdata = portal.json()["data"]
    assert "billing.stripe.test" in pdata["portal_url"]
    assert pdata["payment_success"] is False
    assert pdata["paid_billing_complete_claimed"] is False

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
    cdata = checkout.json()["data"]
    assert "checkout.stripe.test" in cdata["checkout_url"]
    assert cdata["payment_success"] is False
    assert cdata["tenant_plan_code_unchanged"] is True
    assert cdata["paid_billing_complete_claimed"] is False

    plan_after = (
        await ac.get("/api/v1/billing/status", headers=headers)
    ).json()["data"]["plan_code"]
    assert plan_after == body["plan_code"]
    assert plan_after in ("trial", "starter", "growth", "enterprise")


async def test_soak_subscription_lifecycle_and_gate_on(client, db_session, monkeypatch):
    """Signed webhooks drive mirror lifecycle; gate ON enforces allowlist."""
    ac, seed = client
    headers = await _super(ac, seed)
    _enable_mock_provider(monkeypatch, gate=True)
    tenant_id = seed["t1"].id
    plan_before = seed["t1"].plan_code
    sub_id = f"sub_soak_{tenant_id[:8]}"

    sale = await ac.post(
        "/api/v1/sales",
        headers=_company_headers(headers, seed),
        json={
            "party_id": seed["party1"].id,
            "subtotal": 3,
            "tax": 0,
            "total": 3,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 403, sale.text
    assert sale.json()["detail"]["code"] == "PAID_BILLING_ENTITLEMENT_DENIED"
    assert sale.json()["detail"]["payment_success"] is False

    created = await _post_webhook(
        ac,
        {
            "id": "evt_soak_created",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": sub_id,
                    "status": "incomplete",
                    "metadata": {"tenant_id": tenant_id, "plan_code": "starter"},
                    "cancel_at_period_end": False,
                }
            },
        },
    )
    assert created.status_code == 200, created.text
    cbody = created.json()["data"]
    assert cbody["payment_success"] is False
    assert cbody["tenant_plan_code_unchanged"] is True
    assert cbody["subscription_mirrored"] is True
    assert cbody["processing_status"] == "mirrored"

    sale2 = await ac.post(
        "/api/v1/sales",
        headers=_company_headers(headers, seed),
        json={
            "party_id": seed["party1"].id,
            "subtotal": 3,
            "tax": 0,
            "total": 3,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale2.status_code == 403, sale2.text

    active = await _post_webhook(
        ac,
        {
            "id": "evt_soak_active",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": sub_id,
                    "status": "active",
                    "metadata": {"tenant_id": tenant_id, "plan_code": "starter"},
                    "cancel_at_period_end": False,
                    "current_period_end": int(time.time()) + 86400 * 30,
                }
            },
        },
    )
    assert active.status_code == 200, active.text
    assert active.json()["data"]["payment_success"] is False

    sale_ok = await ac.post(
        "/api/v1/sales",
        headers=_company_headers(headers, seed),
        json={
            "party_id": seed["party1"].id,
            "subtotal": 8,
            "tax": 0,
            "total": 8,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale_ok.status_code == 200, sale_ok.text

    patch_ok = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}",
        headers=headers,
        json={"name": "Alpha Co Soak Active"},
    )
    assert patch_ok.status_code == 200, patch_ok.text

    past = await _post_webhook(
        ac,
        {
            "id": "evt_soak_past_due",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": sub_id,
                    "status": "past_due",
                    "metadata": {"tenant_id": tenant_id},
                }
            },
        },
    )
    assert past.status_code == 200, past.text
    sale_deny = await ac.post(
        "/api/v1/sales",
        headers=_company_headers(headers, seed),
        json={
            "party_id": seed["party1"].id,
            "subtotal": 3,
            "tax": 0,
            "total": 3,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale_deny.status_code == 403, sale_deny.text
    assert sale_deny.json()["detail"]["deny_reason"] == "subscription_status_denied"

    canceled = await _post_webhook(
        ac,
        {
            "id": "evt_soak_canceled",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": sub_id,
                    "status": "canceled",
                    "metadata": {"tenant_id": tenant_id},
                }
            },
        },
    )
    assert canceled.status_code == 200, canceled.text
    patch_deny = await ac.patch(
        f"/api/v1/companies/{seed['c1'].id}",
        headers=headers,
        json={"name": "Should Block"},
    )
    assert patch_deny.status_code == 403, patch_deny.text

    await db_session.refresh(seed["t1"])
    assert seed["t1"].plan_code == plan_before

    status = await ac.get("/api/v1/billing/status", headers=headers)
    subs = status.json()["data"]["subscriptions"]
    assert any(s["provider_subscription_id"] == sub_id for s in subs)
    assert all(s.get("payment_success") is False for s in subs)


async def test_soak_checkout_completed_and_invoice_paid_no_completes(
    client, db_session, monkeypatch
):
    ac, seed = client
    headers = await _super(ac, seed)
    _enable_mock_provider(monkeypatch, gate=False)
    tenant_id = seed["t1"].id
    plan_before = seed["t1"].plan_code
    sub_id = f"sub_invoice_{tenant_id[:8]}"

    customer = await billing_svc.ensure_billing_customer(
        db_session, tenant_id=tenant_id, email="soak@alpha.example.com"
    )
    customer.provider_customer_id = f"cus_soak_{tenant_id[:8]}"
    await db_session.commit()

    cs = await _post_webhook(
        ac,
        {
            "id": "evt_soak_cs_completed",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_soak_1",
                    "customer": customer.provider_customer_id,
                    "subscription": sub_id,
                    "payment_status": "paid",
                    "client_reference_id": tenant_id,
                    "metadata": {"tenant_id": tenant_id, "plan_code": "growth"},
                }
            },
        },
    )
    assert cs.status_code == 200, cs.text
    cs_data = cs.json()["data"]
    assert cs_data["payment_success"] is False
    assert cs_data["payment_processed"] is False
    assert cs_data["tenant_plan_code_unchanged"] is True
    assert cs_data["subscription_mirrored"] is True
    assert cs_data["paid_billing_complete_claimed"] is False
    assert cs_data["checkout_success_claimed"] is False

    inv = await _post_webhook(
        ac,
        {
            "id": "evt_soak_invoice_paid",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_soak_1",
                    "customer": customer.provider_customer_id,
                    "subscription": sub_id,
                    "period_end": int(time.time()) + 86400 * 30,
                    "metadata": {"tenant_id": tenant_id},
                    "lines": {
                        "data": [
                            {
                                "period": {
                                    "end": int(time.time()) + 86400 * 30,
                                }
                            }
                        ]
                    },
                }
            },
        },
    )
    assert inv.status_code == 200, inv.text
    inv_data = inv.json()["data"]
    assert inv_data["payment_success"] is False
    assert inv_data["processing_status"] == "recorded_invoice_paid_no_complete"
    assert inv_data["tenant_plan_code_unchanged"] is True

    await db_session.refresh(seed["t1"])
    assert seed["t1"].plan_code == plan_before

    row = (
        await db_session.execute(
            select(m.TenantBillingSubscription).where(
                m.TenantBillingSubscription.provider_subscription_id == sub_id
            )
        )
    ).scalar_one()
    assert row.metadata_json.get("payment_success") is False
    assert row.metadata_json.get("invoice_paid_recorded") is True
    assert billing_svc.serialize_subscription(row)["payment_success"] is False


async def test_soak_idempotent_signed_webhook_replay(client, monkeypatch):
    ac, seed = client
    await _super(ac, seed)
    _enable_mock_provider(monkeypatch, gate=True)
    tenant_id = seed["t1"].id
    payload = {
        "id": "evt_soak_idempotent",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": f"sub_idem_{tenant_id[:8]}",
                "status": "trialing",
                "metadata": {"tenant_id": tenant_id},
            }
        },
    }
    first = await _post_webhook(ac, payload)
    second = await _post_webhook(ac, payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["duplicate"] is True
    assert second.json()["data"]["payment_success"] is False


def test_soak_company_ui_and_ops_docs_honesty():
    company = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "billing/portal-session" in company
    assert "billing/checkout-session" in company
    assert "Complete remains MISSING" in company or "Complete still MISSING" in company

    adr = (ROOT / "docs/ADR_002_PAID_BILLING_SCAFFOLD.md").read_text(encoding="utf-8")
    assert "test_paid_billing_soak.py" in adr
    assert "ops-blocked" in adr.lower() or "Complete" in adr

    checklist = (ROOT / "docs/paid_billing_staging_soak_checklist.md").read_text(
        encoding="utf-8"
    )
    assert "PAID_BILLING_ENTITLEMENT_GATE_ENABLED" in checklist
    assert "Complete" in checklist
    assert "live" in checklist.lower()
