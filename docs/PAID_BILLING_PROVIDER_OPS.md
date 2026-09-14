# Paid billing provider ops (ADR-002 — PARTIAL)

**Honesty:** Configuring these env vars does **not** claim paid billing Complete, checkout Complete, live subscriptions, or fabricated MRR. ADR-002 remains in force until a verified live provider cutover with evidence.

See [`ADR_002_PAID_BILLING_SCAFFOLD.md`](ADR_002_PAID_BILLING_SCAFFOLD.md).

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `BILLING_PROVIDER` | empty | Provider name when intentionally configured (e.g. `stripe`) |
| `BILLING_PROVIDER_SECRET_KEY` | empty | Provider secret (never commit). Required for portal/checkout create. |
| `BILLING_PROVIDER_WEBHOOK_SECRET` | empty | Stripe-compatible webhook signing secret (`t=…,v1=…`) |
| `BILLING_PROVIDER_PORTAL_RETURN_URL` | empty | Default return URL when portal request omits `return_url` |
| `BILLING_PROVIDER_CHECKOUT_SUCCESS_URL` | empty | Default Checkout Session success URL |
| `BILLING_PROVIDER_CHECKOUT_CANCEL_URL` | empty | Default Checkout Session cancel URL (falls back to success URL) |
| `BILLING_PROVIDER_PRICE_IDS` | empty | JSON map `plan_code` → Stripe price id (required for live checkout unless body `price_id`) |
| `BILLING_PROVIDER_MODE` | empty | `mock` (CI), `live` (provider API), or empty (auto: mock if secret starts with `sk_test_mock` / `sk_mock_`, else live) |
| `BILLING_PROVIDER_API_BASE` | `https://api.stripe.com` | Override for tests / proxies |
| `BILLING_CHECKOUT_ENABLED` | `false` | Honesty Complete non-claim; session create still follows provider keys |
| `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` | `false` | Arms future entitlement sync; **legacy trial/grace/suspend remains authoritative** |

## Fail-closed behavior

| State | Portal Session | Checkout Session | Webhook |
|-------|----------------|------------------|---------|
| Keys unset | HTTP **503** — clear error (no fake `portal_url`) | HTTP **503** (no fake `checkout_url`) | Events may be recorded; signature not enforced — set webhook secret before staging |
| Mock mode | Deterministic mock `portal_url` (not payment success) | Deterministic mock `checkout_url` (not payment success) | Same as configured |
| Live keys | Creates Stripe Billing Portal Session; **502** if provider fails | Creates Stripe Checkout Session when price present; **400** if price missing; **502** if provider fails | Signature required when webhook secret set |
| Charge / upgrade | Never returns `payment_success` | Never auto-upgrades `Tenant.plan_code` | Mirrors subscription objects locally only; does **not** mutate `Tenant.plan_code` |

## Staging checklist (not Complete)

1. Set `BILLING_PROVIDER=stripe` + secret key + webhook secret in staging secrets manager (not git).
2. Set `BILLING_PROVIDER_MODE=live` (or leave auto with a non-mock secret).
3. Set `BILLING_PROVIDER_PRICE_IDS` JSON for paid plans (or pass `price_id` per request).
4. Point provider webhook to `POST /api/v1/billing/webhooks/provider`.
5. Confirm signed event lands in `billing_webhook_events` with `signature_valid=true`.
6. Confirm `POST /api/v1/billing/portal-session` returns a real `portal_url` and Company UI navigates to it.
7. Confirm `POST /api/v1/billing/checkout-session` returns a real `checkout_url` and Company UI navigates to it.
8. Confirm Checkout / `invoice.paid` does **not** mutate `Tenant.plan_code`.
9. Confirm `GET /api/v1/billing/status` still reports `paid_billing_complete_claimed=false` and `checkout_enabled=false`.
10. Do **not** enable `PAID_BILLING_ENTITLEMENT_GATE_ENABLED` in production until mirror→access evidence exists.
11. Do **not** claim paid billing Complete from this checklist alone.

## CI / mock

```bash
BILLING_PROVIDER=stripe
BILLING_PROVIDER_SECRET_KEY=sk_test_mock_ci
BILLING_PROVIDER_MODE=mock
```

Mock portal URLs use host `billing.stripe.test`. Mock checkout URLs use host `checkout.stripe.test`. Neither claims payment success.

## Related surfaces

- Tenant: `GET /api/v1/billing/status`, `POST /api/v1/billing/portal-session`, `POST /api/v1/billing/checkout-session`
- Platform: `GET /api/v1/platform/billing` (metadata roster + honesty)
- Plan metadata: `PATCH /api/v1/tenants/me` `plan_code` (still metadata-only)
- Company UI: opens `portal_url` / `checkout_url` when present; surfaces 503/502/400 errors clearly
