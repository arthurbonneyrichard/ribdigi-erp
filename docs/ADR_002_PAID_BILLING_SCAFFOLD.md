# ADR-002 Paid Billing Scaffold (PARTIAL — not Complete)

**Status:** PARTIAL scaffold  
**Date:** 2026-09-14  
**Related:** [`ADR_002_BILLING_DEFERRED.md`](ADR_002_BILLING_DEFERRED.md) · [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) · [`BILLING_REMAINING_GATE_MVP.md`](BILLING_REMAINING_GATE_MVP.md)

## What landed

Engineering scaffold toward paid billing, extending existing `plan_code` / `PLAN_CATALOG` / platform billing honesty surfaces:

| Layer | Delivered |
|-------|-----------|
| Schema | `tenant_billing_customers`, `tenant_billing_subscriptions`, `billing_webhook_events` (`20260914_0114`) |
| Models | `TenantBillingCustomer`, `TenantBillingSubscription`, `BillingWebhookEvent` |
| Service | `backend/app/billing_provider.py` |
| APIs | `GET /billing/status`, `POST /billing/portal-session`, `POST /billing/webhooks/provider` |
| Platform | `GET /platform/billing` includes scaffold honesty flags |
| Flag | `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` default **false** |
| Ops | [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) |
| Tests | `backend/tests/test_paid_billing_scaffold.py` |

## What did **not** land

- Live Stripe (or other) Checkout / Billing Portal Session API calls
- Card charges, invoices, or fabricated payment success
- Fabricated MRR / live subscriptions Completes
- Entitlement gate applying provider status as authoritative access control
- Mutation of `Tenant.plan_code` / max_* caps from webhooks
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

## Next cutover steps (separate Completes)

1. Configure provider keys in staging (ops doc) + signed webhook proof
2. Implement live Billing Portal Session create (still no fake success)
3. Wire entitlement gate ON only after mirror→access evidence (do not claim Complete from flag alone)
4. Checkout Session / paid upgrade path with real provider receipts
5. Evidence pack before flipping Complete flags

Offline Complete / 7-day VERIFIED / go-live / ADR-005 Complete remain **MISSING**.
Paid billing Complete remains **MISSING**.
