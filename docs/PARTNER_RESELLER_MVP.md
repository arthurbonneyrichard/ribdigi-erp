# Partner / Reseller Terms MVP — Channel Honesty Packaging

**Status:** Complete (MVP) — Stage 49 R1  
**Evidence:** `backend/tests/test_partner_reseller_r1.py` · `/opt/cursor/artifacts/launch/stage49_r1_partner_reseller.json`  
**Register:** `ops/mvp/partner-reseller.json`  
**Related:** [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md) · [TOS_AUP_MVP.md](TOS_AUP_MVP.md) · [MSA_ADDENDUM_MVP.md](MSA_ADDENDUM_MVP.md) · [BILLING_DEFERRED_HONESTY_MVP.md](BILLING_DEFERRED_HONESTY_MVP.md) · [PROFESSIONAL_SERVICES_SOW_MVP.md](PROFESSIONAL_SERVICES_SOW_MVP.md) · [DEFERRED_ADR_REGISTER_MVP.md](DEFERRED_ADR_REGISTER_MVP.md) · [STAGE_49_PLAN.md](STAGE_49_PLAN.md) · [ADR_103_STAGE49_OPEN.md](ADR_103_STAGE49_OPEN.md)

This is the **MVP Partner / Reseller Terms honesty packaging surface**: a customer-facing channel boundary consolidating PRODUCT_OVERVIEW white-label / reseller themes with Stage 43 ToS / Stage 39 MSA adjacency into a partner / reseller honesty pack. It does **not** claim a live partner program Complete, signed reseller agreement Complete, white-label live Complete, or channel commission Complete.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Partner / reseller step indexed to Complete (MVP) commercial / legal surfaces |
| `remaining` | Live partner program / signed reseller / white-label still required |

Every step keeps `done: false`. Top-level `partner_program_live: false` / `signed_reseller_agreement_claimed: false` / `white_label_live_claimed: false` / `channel_commission_claimed: false`.

## Register scope

1. PRODUCT_OVERVIEW white-label / reseller theme adjacency.
2. Stage 43 ToS / AUP legal-notice adjacency.
3. Stage 39 MSA security addendum commercial adjacency.
4. Stage 36 billing-deferred adjacency (billing ≠ channel program).
5. Stage 48 professional services / SOW adjacency (direct SOW ≠ reseller).
6. Deferred ADR register / ADR-002 billing-deferred adjacency.
7. DEVELOPMENT_ROADMAP white-label / ecosystem backlog adjacency.
8. Stage 49 plan honesty Remaining surfaces.
9. Live partner program Remaining.
10. Signed reseller / white-label Remaining.

## Automation hooks

1. Maintain `ops/mvp/partner-reseller.json` (synced by `test_partner_reseller_r1.py`).
2. Align honesty with Stage 36 billing-deferred and Stage 43 ToS Remaining flags.
3. CI proves packaging honesty only — never forges live partner program or signed reseller Complete.

## Explicitly not claimed

- Live partner program Complete because Stage 49 R1 packaging exists
- Signed reseller agreement Complete
- White-label / OEM channel live Complete
- Channel commission / revenue-share Complete
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 36–48 billing / ToS / SOW packs as new runtime Complete

## Sign-off

Stage 49 R1 is met when this doc + register JSON + evidence JSON exist, `test_partner_reseller_r1.py` passes, and LAUNCH_CHECKLIST / PRODUCTION_READINESS / plan / roadmap cite Stage 49 R1 without inventing live partner program / signed reseller Complete.
