# ADR-002: Subscription Billing Deferred for Commercial MVP

**Status:** Accepted  
**Date:** 2026-08-09

## Context

BR-1.3 requires upgrade/downgrade plan capability. Charging cards, invoicing subscriptions, or returning fake payment success would violate the commercial MVP rule against placeholder business logic presented as complete.

## Decision

For Stage 1 / Commercial MVP:

1. `tenants.plan_code` is **commercial metadata** only (`trial` | `starter` | `growth` | `enterprise`).
2. Admins may change `plan_code` via `PATCH /tenants/me` for labeling and future entitlement hooks.
3. **No payment provider**, checkout, or charge is invoked. Responses must not claim payment success.
4. Tenant serialize includes `billing_deferred: true` and `billing_provider: null`.
5. Plan changes are audited as `plan_code_changed` (from → to) in addition to `profile_update`.
6. Trial / grace / suspend lifecycle (BR-1.3 status ACs) remains the enforced commercial gate for access.
7. Paid upgrade/downgrade with a real billing provider is **post-MVP**.

## Consequences

- Product honesty: UI and API state that billing is deferred.
- Entitlement enforcement by plan can be added later without rewriting trial lifecycle.
- BR-1.3 “upgrade/downgrade” is PARTIAL until a billing provider ships; metadata change is the Stage 1 closeout.

**2026-09-14 scaffold + portal/checkout create:** Engineering tables/APIs for provider customer, subscription mirror, webhook inbox, Portal + Checkout Session create (live when keys configured; mock for CI; 503 when unconfigured) landed as **PARTIAL** — see [`ADR_002_PAID_BILLING_SCAFFOLD.md`](ADR_002_PAID_BILLING_SCAFFOLD.md).

**2026-09-15 Phase E mock soak:** Automated mock-provider soak (`test_paid_billing_soak.py`) proves portal/checkout/webhook lifecycle + entitlement gate ON allowlist + `invoice.paid` non-Complete. Entitlement gate flag defaults OFF. Paid billing Complete / checkout success / fabricated MRR remain **MISSING** — **ops-blocked** on live Stripe keys + [`paid_billing_staging_soak_checklist.md`](paid_billing_staging_soak_checklist.md) (mock evidence ≠ Complete).

See also Stage 180 go-live remaining-gate index: [`GOLIVE_REMAINING_GATE_MVP.md`](GOLIVE_REMAINING_GATE_MVP.md) (billing remains deferred).

See also Stage 181 billing remaining-gate index: [`BILLING_REMAINING_GATE_MVP.md`](BILLING_REMAINING_GATE_MVP.md) (billing remains deferred; not Complete).
