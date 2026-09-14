# Paid billing staging soak checklist (ADR-002)

**Status:** Engineering mock soak **ready** (`test_paid_billing_soak.py`).
Paid billing Complete remains **MISSING** — **ops-blocked** on live Stripe keys +
this staging evidence pack.

**Honesty:** Checking boxes here does **not** authorize Offline Complete,
7-day VERIFIED, go-live, ADR-005 Complete, or fabricated `payment_success`.

Analogous to SEC-M2 Phase E: automated mock evidence closes the engineering
path; production/live provider enable is a separate ops cutover.

See [`PAID_BILLING_PROVIDER_OPS.md`](PAID_BILLING_PROVIDER_OPS.md) ·
[`ADR_002_PAID_BILLING_SCAFFOLD.md`](ADR_002_PAID_BILLING_SCAFFOLD.md) ·
[`GO_LIVE_READINESS_CHECKLIST.md`](GO_LIVE_READINESS_CHECKLIST.md).

## Already proven in CI (mock provider)

- [x] Portal Session create (`BILLING_PROVIDER_MODE=mock`) → `billing.stripe.test` URL
- [x] Checkout Session create (mock) → `checkout.stripe.test` URL; no plan upgrade
- [x] Signed webhook ingest (valid / invalid / idempotent)
- [x] Subscription lifecycle mirror: created → active → past_due → canceled
- [x] `checkout.session.completed` + `invoice.paid` recorded **without**
      `payment_success` / `Tenant.plan_code` mutation
- [x] Entitlement gate ON allowlist: `POST /sales`, `PATCH /companies/{id}`
      (`active`/`trialing` allow; missing/`past_due`/`canceled` deny)
- [x] Prod examples keep `PAID_BILLING_ENTITLEMENT_GATE_ENABLED=false` and
      `BILLING_CHECKOUT_ENABLED=false`

Evidence: `backend/tests/test_paid_billing_soak.py` (+ scaffold suite).

## Staging (live Stripe) — required before any Complete claim

1. [ ] Place **real** Stripe secret + webhook signing secret in secrets manager
      (never git). Do **not** use `sk_test_mock*` prefixes.
2. [ ] Set `BILLING_PROVIDER=stripe`, `BILLING_PROVIDER_MODE=live` (or auto).
3. [ ] Set `BILLING_PROVIDER_PRICE_IDS` JSON for paid plans + portal/checkout URLs.
4. [ ] Point Stripe webhook to `POST /api/v1/billing/webhooks/provider`
      (events: `customer.subscription.*`, `checkout.session.completed`,
      `invoice.paid`).
5. [ ] Confirm signed event lands with `signature_valid=true`.
6. [ ] Company UI: Open billing portal → real Stripe portal URL.
7. [ ] Company UI: Checkout → real Checkout Session URL; complete a **test-mode**
      card charge in Stripe test mode.
8. [ ] Confirm webhook updates local subscription mirror; confirm
      `Tenant.plan_code` **unchanged** after Checkout / `invoice.paid`.
9. [ ] Confirm `GET /billing/status` still reports
      `paid_billing_complete_claimed=false`, `checkout_enabled=false`,
      `payment_success=false` on subscription rows.
10. [ ] Staging-only: enable `PAID_BILLING_ENTITLEMENT_GATE_ENABLED=true`.
11. [ ] Gate ON: `active`/`trialing` allows gated writes; `past_due`/`canceled`/
      missing → `403 PAID_BILLING_ENTITLEMENT_DENIED`.
12. [ ] Rollback: set gate `false`; legacy trial/grace/suspend returns.
13. [ ] **Do not** claim paid billing Complete from this checklist alone —
      commercial acceptance + owner sign-off still required, and
      `BILLING_CHECKOUT_ENABLED` Complete flag stays false until then.

## Explicit non-claims

| Claim | Status |
|-------|--------|
| Paid billing Complete | **MISSING** (ops-blocked) |
| `payment_success` Complete | **MISSING** |
| Live subscriptions / fabricated MRR | **MISSING** / banned |
| Offline Complete / 7-day VERIFIED / go-live | **MISSING** |
| ADR-005 membership Complete | **Complete** (flag default OFF) |
