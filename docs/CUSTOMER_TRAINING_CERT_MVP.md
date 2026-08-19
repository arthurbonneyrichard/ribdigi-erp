# Customer Training / Certification MVP — Training Honesty Packaging

**Status:** Complete (MVP) — Stage 48 T1  
**Evidence:** `backend/tests/test_customer_training_cert_t1.py` · `/opt/cursor/artifacts/launch/stage48_t1_customer_training_cert.json`  
**Register:** `ops/mvp/customer-training-cert.json`  
**Related:** [KNOWLEDGE_TRANSFER_MVP.md](KNOWLEDGE_TRANSFER_MVP.md) · [PRODUCT_OVERVIEW.md](PRODUCT_OVERVIEW.md) · [PROFESSIONAL_SERVICES_SOW_MVP.md](PROFESSIONAL_SERVICES_SOW_MVP.md) · [FIRST_TENANT_ONBOARDING_MVP.md](FIRST_TENANT_ONBOARDING_MVP.md) · [SUPPORT_SLA_BOUNDARY_MVP.md](SUPPORT_SLA_BOUNDARY_MVP.md) · [SUPPORT_RUNBOOK_MVP.md](SUPPORT_RUNBOOK_MVP.md) · [STAGE_48_PLAN.md](STAGE_48_PLAN.md) · [ADR_101_STAGE48_OPEN.md](ADR_101_STAGE48_OPEN.md)

This is the **MVP Customer Training / Certification honesty packaging surface**: a customer-facing training boundary consolidating Stage 33 knowledge-transfer and PRODUCT_OVERVIEW on-site training themes with Stage 48 P1 professional-services adjacency into a training / certification honesty pack. It does **not** claim live customer training Complete, attendance certification Complete, or that training delivery has already been executed for paying customers.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Customer training / certification step indexed to Complete (MVP) knowledge-transfer / commercial surfaces |
| `remaining` | Live training / attendance certification still required |

Every step keeps `done: false`. Top-level `customer_training_delivered_claimed: false` / `live_training_claimed: false` / `training_complete_claimed: false` / `training_certification_claimed: false`.

## Register scope

1. Stage 33 knowledge-transfer curriculum adjacency (operator ≠ customer cert).
2. PRODUCT_OVERVIEW on-site / training theme adjacency.
3. Stage 48 P1 professional services / SOW adjacency (services ≠ training cert).
4. Stage 33 first-tenant onboarding adjacency.
5. Stage 36 support SLA / support runbook adjacency.
6. BUSINESS_REQUIREMENTS training-material adjacency.
7. Stage 30 support / admin runbook adjacency.
8. Stage 48 plan honesty Remaining surfaces.
9. Live customer training Remaining.
10. Attendance / certification Remaining.

## Automation hooks

1. Maintain `ops/mvp/customer-training-cert.json` (synced by `test_customer_training_cert_t1.py`).
2. Align honesty with Stage 33 knowledge-transfer Remaining flags (`live_training_claimed` / `training_complete_claimed` stay false).
3. CI proves packaging honesty only — never forges live customer training or attendance cert Complete.

## Explicitly not claimed

- Live customer training Complete because Stage 48 T1 packaging exists
- Training attendance certification Complete
- Signed training attendance Complete
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 33–47 knowledge-transfer / support packs as new runtime Complete

## Sign-off

Stage 48 T1 is met when this doc + register JSON + evidence JSON exist, `test_customer_training_cert_t1.py` passes, and LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / plan cite Stage 48 T1 without inventing live training / attendance cert Complete.

See also Stage 189 live-training remaining-gate index: [`LIVE_TRAINING_REMAINING_GATE_MVP.md`](LIVE_TRAINING_REMAINING_GATE_MVP.md).
