# ADR-002 Paid Billing Scaffold (PARTIAL — not Complete)

**Status:** PARTIAL  
**Date:** 2026-09-14 (portal session create advance)  
**Related:** [`ADR_002_BILLING_DEFERRED.md`](ADR_002_BILLING_DEFERRED.md) · [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) · [`BILLING_REMAINING_GATE_MVP.md`](BILLING_REMAINING_GATE_MVP.md)

## What landed

Engineering toward paid billing, extending existing `plan_code` / `PLAN_CATALOG` / platform billing honesty surfaces:

| Layer | Delivered |
|-------|-----------|
| Schema | `tenant_billing_customers`, `tenant_billing_subscriptions`, `billing_webhook_events` (`20260914_0114`) |
| Models | `TenantBillingCustomer`, `TenantBillingSubscription`, `BillingWebhookEvent` |
| Service | `backend/app/billing_provider.py` |
| APIs | `GET /billing/status`, `POST /billing/portal-session` (real create when configured), `POST /billing/webhooks/provider` |
| Portal | Live Stripe Billing Portal Session create when keys + `BILLING_PROVIDER_MODE=live` (or auto); **mock mode for CI**; **503 when unconfigured** (no fake success) |
| Platform | `GET /platform/billing` includes honesty flags |
| Flag | `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` default **false** |
| Ops | [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) |
| Tests | `backend/tests/test_paid_billing_scaffold.py` (portal mock/live/fail-closed + signed webhook proof) |

## What did **not** land

- Checkout Session / card charges / fabricated payment success
- Fabricated MRR / live subscriptions Completes
- Entitlement gate applying provider status as authoritative access control
- Mutation of `Tenant.plan_code` / max_* caps from webhooks (including `invoice.paid`)
- Paid billing Complete / go-live Complete

## Honesty flags (must stay false until live provider + verification)

```text
paid_billing_complete_claimed: false
checkout_success_claimed: false
payment_provider_live_claimed: false
subscriptions_live_claimed: false
mrr_fabricated_claimed: false
billing_deferred: true
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

Opening a portal URL is **not** payment success and does **not** claim paid billing Complete.

## Next cutover steps (separate Completes)

1. Staging: real provider keys + signed webhook proof evidence pack
2. Checkout Session / paid upgrade path with real provider receipts
3. Wire entitlement gate ON only after mirror→access evidence (do not claim Complete from flag alone)
4. Evidence pack before flipping Complete flags

Offline Complete / 7-day VERIFIED / go-live / ADR-005 Complete remain **MISSING**.  
Paid billing Complete remains **MISSING**.
