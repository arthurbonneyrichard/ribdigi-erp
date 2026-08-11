# Referral Program MVP — Acquisition Honesty Packaging

**Status:** Complete (MVP) — Stage 50 R1  
**Evidence:** `backend/tests/test_referral_program_r1.py` · `/opt/cursor/artifacts/launch/stage50_r1_referral_program.json`  
**Register:** `ops/mvp/referral-program.json`  
**Related:** [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md) · [BILLING_DEFERRED_HONESTY_MVP.md](BILLING_DEFERRED_HONESTY_MVP.md) · [PARTNER_RESELLER_MVP.md](PARTNER_RESELLER_MVP.md) · [PRICING_TRANSPARENCY_MVP.md](PRICING_TRANSPARENCY_MVP.md) · [TOS_AUP_MVP.md](TOS_AUP_MVP.md) · [DEFERRED_ADR_REGISTER_MVP.md](DEFERRED_ADR_REGISTER_MVP.md) · [STAGE_50_PLAN.md](STAGE_50_PLAN.md) · [ADR_105_STAGE50_OPEN.md](ADR_105_STAGE50_OPEN.md)

This is the **MVP Referral Program honesty packaging surface**: a customer-facing acquisition boundary consolidating PRODUCT_OVERVIEW referral-program themes with Stage 36 billing-deferred adjacency into a referral honesty pack. It does **not** claim a live referral program Complete, referral credits Complete, referral payout Complete, or free-month credit live Complete.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Referral program step indexed to Complete (MVP) commercial / billing-deferred surfaces |
| `remaining` | Live referral credits / payout / free-month credit still required |

Every step keeps `done: false`. Top-level `referral_program_live: false` / `referral_credits_claimed: false` / `referral_payout_claimed: false` / `free_month_credit_live: false`.

## Register scope

1. PRODUCT_OVERVIEW referral-program acquisition themes.
2. Stage 36 billing-deferred honesty adjacency (credits ≠ paid billing Complete).
3. Stage 49 partner / reseller adjacency (reseller ≠ referral program).
4. Stage 49 pricing transparency adjacency (list price ≠ referral credit).
5. Stage 43 ToS / AUP commercial-notice adjacency.
6. Deferred ADR register / ADR-002 billing-deferred adjacency.
7. DEVELOPMENT_ROADMAP acquisition / GTM backlog adjacency.
8. Stage 50 plan honesty Remaining surfaces.
9. Live referral credits Remaining.
10. Referral payout / free-month credit Remaining.

## Automation hooks

1. Maintain `ops/mvp/referral-program.json` (synced by `test_referral_program_r1.py`).
2. Align honesty with Stage 36 billing-deferred Remaining flags (`billing_complete_claimed` / `checkout_success_claimed` stay false).
3. CI proves packaging honesty only — never forges live referral credits or payout Complete.

## Explicitly not claimed

- Live referral program Complete because Stage 50 R1 packaging exists
- Referral credits / free-month grant Complete
- Referral payout / commission Complete
- Paid billing Complete (ADR-002)
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 36–49 billing / channel packs as new runtime Complete

## Sign-off

Stage 50 R1 is met when this doc + register JSON + evidence JSON exist, `test_referral_program_r1.py` passes, and LAUNCH_CHECKLIST / PRODUCTION_READINESS / plan / roadmap cite Stage 50 R1 without inventing live referral credits / payout Complete.
