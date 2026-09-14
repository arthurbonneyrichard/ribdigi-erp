# ADR-002 Paid Billing Scaffold (PARTIAL — not Complete)

**Status:** PARTIAL  
**Date:** 2026-09-14 (Checkout Session create advance)  
**Related:** [`ADR_002_BILLING_DEFERRED.md`](ADR_002_BILLING_DEFERRED.md) · [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) · [`BILLING_REMAINING_GATE_MVP.md`](BILLING_REMAINING_GATE_MVP.md)

## What landed

Engineering toward paid billing, extending existing `plan_code` / `PLAN_CATALOG` / platform billing honesty surfaces:

| Layer | Delivered |
|-------|-----------|
| Schema | `tenant_billing_customers`, `tenant_billing_subscriptions`, `billing_webhook_events` (`20260914_0114`) |
| Models | `TenantBillingCustomer`, `TenantBillingSubscription`, `BillingWebhookEvent` |
| Service | `backend/app/billing_provider.py` |
| APIs | `GET /billing/status`, `POST /billing/portal-session`, `POST /billing/checkout-session`, `POST /billing/webhooks/provider` |
| Portal | Live Stripe Billing Portal Session create when keys + mode live; **mock for CI**; **503 when unconfigured** |
| Checkout | Live Stripe Checkout Session create when keys + price; **mock for CI**; **503 when unconfigured**; never auto-upgrades `Tenant.plan_code` |
| Platform | `GET /platform/billing` includes honesty flags |
| Flag | `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` default **false** |
| Ops | [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) |
| Tests | `backend/tests/test_paid_billing_scaffold.py` (portal + checkout + signed webhook proof) |

## What did **not** land

- Payment success Complete / fabricated `payment_success` responses
- Auto mutation of `Tenant.plan_code` / entitlement caps from Checkout or webhooks (including `invoice.paid`)
- Fabricated MRR / live subscriptions Completes
- Entitlement gate applying provider status as authoritative access control
- Paid billing Complete / go-live Complete

## Honesty flags (must stay false until live provider + verification)

```text
paid_billing_complete_claimed: false
checkout_success_claimed: false
payment_provider_live_claimed: false
subscriptions_live_claimed: false
mrr_fabricated_claimed: false
billing_deferred: true
checkout_enabled: false          # Complete non-claim (session create ≠ Complete)
scaffold_status: partial
operational_gate: trial_grace_suspend_lifecycle   # unless gate flag ON (still non-authoritative)
```

`serialize_tenant` still returns `billing_deferred: true` and `billing_provider: null`.

## Portal Session behavior

| Mode | Trigger | Result |
|------|---------|--------|
| unconfigured | keys unset | HTTP **503** — clear error, no `portal_url` soft-success |
| mock | `BILLING_PROVIDER_MODE=mock` or `sk_test_mock*` secret | Deterministic `portal_url` on `billing.stripe.test` (CI) |
| live | keys + mode live/auto | Stripe `/v1/customers` (if needed) + `/v1/billing_portal/sessions`; **502** on provider failure |

## Checkout Session behavior

| Mode | Trigger | Result |
|------|---------|--------|
| unconfigured | keys unset | HTTP **503** — clear error, no `checkout_url` soft-success |
| mock | `BILLING_PROVIDER_MODE=mock` or `sk_test_mock*` secret | Deterministic `checkout_url` on `checkout.stripe.test` (CI) |
| live | keys + price_id (body or `BILLING_PROVIDER_PRICE_IDS`) | Stripe `/v1/customers` (if needed) + `/v1/checkout/sessions`; **400** if price missing; **502** on provider failure |

Creating a Checkout Session URL is **not** payment success, does **not** auto-upgrade `Tenant.plan_code`, and does **not** claim paid billing Complete.

## Next cutover steps (separate Completes)

1. Staging: real provider keys + price map + signed webhook soak evidence pack
2. Wire entitlement gate ON only after mirror→access evidence (do not claim Complete from flag alone)
3. Evidence pack before flipping Complete flags

Offline Complete / 7-day VERIFIED / go-live / ADR-005 Complete remain **MISSING**.  
Paid billing Complete remains **MISSING**.
