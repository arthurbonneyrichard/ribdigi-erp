# ADR-002 Paid Billing Scaffold (PARTIAL — Complete ops-blocked)

**Status:** PARTIAL — engineering mock soak **ready**; paid billing Complete
**MISSING** (ops-blocked on live Stripe keys + staging soak)  
**Date:** 2026-09-15 (Phase E mock soak)  
**Related:** [`ADR_002_BILLING_DEFERRED.md`](ADR_002_BILLING_DEFERRED.md) ·
[`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) ·
[`paid_billing_staging_soak_checklist.md`](paid_billing_staging_soak_checklist.md) ·
[`BILLING_REMAINING_GATE_MVP.md`](BILLING_REMAINING_GATE_MVP.md)

## What landed

Engineering toward paid billing, extending existing `plan_code` / `PLAN_CATALOG` /
platform billing honesty surfaces:

| Layer | Delivered |
|-------|-----------|
| Schema | `tenant_billing_customers`, `tenant_billing_subscriptions`, `billing_webhook_events` (`20260914_0114`) |
| Models | `TenantBillingCustomer`, `TenantBillingSubscription`, `BillingWebhookEvent` |
| Service | `backend/app/billing_provider.py` |
| APIs | `GET /billing/status`, `POST /billing/portal-session`, `POST /billing/checkout-session`, `POST /billing/webhooks/provider` |
| Portal | Live Stripe Billing Portal Session create when keys + mode live; **mock for CI**; **503 when unconfigured** |
| Checkout | Live Stripe Checkout Session create when keys + price; **mock for CI**; **503 when unconfigured**; never auto-upgrades `Tenant.plan_code` |
| Webhooks | Signed ingest; subscription lifecycle mirror; `checkout.session.completed` + `invoice.paid` recorded **without** payment_success / plan_code mutation |
| Platform | `GET /platform/billing` includes honesty flags |
| Flag | `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` default **false** |
| Entitlement gate (when ON) | Provider subscription mirror authoritative **only** for documented gated routes (see below) |
| Ops | [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) · [`paid_billing_staging_soak_checklist.md`](paid_billing_staging_soak_checklist.md) |
| Tests | `test_paid_billing_scaffold.py` + **Phase E** `test_paid_billing_soak.py` (mock portal/checkout + signed lifecycle + gate ON + invoice.paid non-Complete) |

## Phase E (engineering soak — analogous to SEC-M2 FIXED pattern)

Automated mock-provider soak proves portal + checkout + signed webhook lifecycle
+ entitlement gate ON allow/deny + no fabricated Completes. Flag defaults stay
**OFF**. This closes the **engineering path**; it does **not** flip paid billing
Complete (live Stripe keys + staging checklist still required — ops-blocked).

| Evidence | Path |
|----------|------|
| Mock soak suite | `backend/tests/test_paid_billing_soak.py` |
| Scaffold suite | `backend/tests/test_paid_billing_scaffold.py` |
| Staging ops | `docs/paid_billing_staging_soak_checklist.md` |

## Entitlement gate allowlist (flag ON only)

When `PAID_BILLING_ENTITLEMENT_GATE_ENABLED=true`, these mutations require a local
subscription mirror with status in `{active, trialing}`:

| Method + path | Notes |
|---------------|-------|
| `POST /api/v1/sales` | Legacy create-sale write |
| `PATCH /api/v1/companies/{company_id}` | Company admin profile mutation |

Deny (HTTP 403 `PAID_BILLING_ENTITLEMENT_DENIED`) when mirror is missing or status is
`past_due` / `canceled` / `cancelled` / other non-allow statuses.

Flag **OFF** (production default): gate is a no-op; trial/grace/suspend lifecycle
remains authoritative for write access. Enabling the flag does **not** claim paid
billing Complete.

## What did **not** land

- Payment success Complete / fabricated `payment_success` responses
- Auto mutation of `Tenant.plan_code` / entitlement caps from Checkout or webhooks (including `invoice.paid`)
- Fabricated MRR / live subscriptions Completes
- Global entitlement enforcement on all ERP writes (only the allowlist above)
- Paid billing Complete / go-live Complete (ops-blocked on live Stripe)

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
engineering_mock_soak_ready: true
paid_billing_complete_ops_blocked: true
paid_billing_complete_blocker: live_stripe_keys_and_staging_soak
operational_gate: trial_grace_suspend_lifecycle
  # when gate flag ON:
  #   provider_subscription_mirror_authoritative_for_gated_routes
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

## Webhook lifecycle behavior

| Event | Local effect | Non-claims |
|-------|--------------|------------|
| `customer.subscription.*` | Upsert subscription mirror status/period | No plan_code mutation; `payment_success=false` |
| `checkout.session.completed` | Seed mirror from `subscription` (+ metadata tenant) | No payment_success Complete |
| `invoice.paid` / `invoice.payment_succeeded` | Record + optional mirror period refresh | Status `recorded_invoice_paid_no_complete`; never Complete |

## Why Complete stays MISSING

Real Stripe secret keys, a signed live webhook soak on staging, and commercial
acceptance are required before flipping Complete honesty flags. Mock/CI evidence
is necessary but not sufficient — claiming Complete from mock alone would violate
commercial MVP honesty (no fake payment success presented as complete).

## Next cutover steps (separate Completes)

1. Staging: real provider keys + price map + signed webhook soak evidence pack
   (`docs/paid_billing_staging_soak_checklist.md`)
2. Enable entitlement gate ON in staging only after mirror→access evidence on the allowlist (do not claim Complete from flag alone)
3. Owner commercial acceptance before flipping Complete flags / `BILLING_CHECKOUT_ENABLED`

Offline Complete / 7-day VERIFIED / go-live / ADR-005 Complete remain **MISSING**.  
Paid billing Complete remains **MISSING** (ops-blocked).
