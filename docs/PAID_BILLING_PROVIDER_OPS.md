# Paid billing provider ops (ADR-002 scaffold — PARTIAL)

**Honesty:** Configuring these env vars does **not** claim paid billing Complete, checkout Complete, live subscriptions, or fabricated MRR. ADR-002 remains in force until a verified live provider cutover with evidence.

See [`ADR_002_PAID_BILLING_SCAFFOLD.md`](ADR_002_PAID_BILLING_SCAFFOLD.md).

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `BILLING_PROVIDER` | empty | Provider name when intentionally configured (e.g. `stripe`) |
| `BILLING_PROVIDER_SECRET_KEY` | empty | Provider secret (never commit). Scaffold does **not** call the provider API yet. |
| `BILLING_PROVIDER_WEBHOOK_SECRET` | empty | Stripe-compatible webhook signing secret (`t=…,v1=…`) |
| `BILLING_PROVIDER_PORTAL_RETURN_URL` | empty | Preferred return URL for a future live portal session |
| `BILLING_CHECKOUT_ENABLED` | `false` | Hard non-claim; scaffold keeps checkout disabled |
| `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` | `false` | Arms future entitlement sync; **legacy trial/grace/suspend remains authoritative** |

## Fail-closed behavior

| State | Portal skeleton | Webhook |
|-------|-----------------|---------|
| Keys unset | `status=not_configured`, `portal_url=null` | Events may be recorded; signature not enforced — set webhook secret before staging |
| Keys set, scaffold only | `status=provider_keys_present_live_call_deferred`, `portal_url=null` | Signature required when webhook secret set |
| Checkout / charge | Never returns `payment_success` / fabricated charge | Mirrors subscription objects locally only; does **not** mutate `Tenant.plan_code` |

## Staging checklist (not Complete)

1. Set `BILLING_PROVIDER=stripe` + secret key + webhook secret in staging secrets manager (not git).
2. Point provider webhook to `POST /api/v1/billing/webhooks/provider`.
3. Confirm signed event lands in `billing_webhook_events` with `signature_valid=true`.
4. Confirm `GET /api/v1/billing/status` still reports `paid_billing_complete_claimed=false`.
5. Do **not** enable `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` in production until mirror→access evidence exists.
6. Do **not** claim paid billing Complete from this checklist alone.

## Related surfaces

- Tenant: `GET /api/v1/billing/status`, `POST /api/v1/billing/portal-session`
- Platform: `GET /api/v1/platform/billing` (metadata roster + scaffold honesty)
- Plan metadata: `PATCH /api/v1/tenants/me` `plan_code` (still metadata-only)
