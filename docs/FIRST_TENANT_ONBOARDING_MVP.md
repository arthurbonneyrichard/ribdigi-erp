# First-Tenant Onboarding MVP — Commercial Tenant Checklist Packaging

**Status:** Complete (MVP) — Stage 33 F1  
**Evidence:** `backend/tests/test_first_tenant_onboarding_f1.py` · `/opt/cursor/artifacts/launch/stage33_f1_first_tenant_onboarding.json`  
**Register:** `ops/mvp/first-tenant-onboarding.json`  
**Related:** [OPERATOR_HANDOFF_MVP.md](OPERATOR_HANDOFF_MVP.md) · [LAUNCH_CHECKLIST.md](LAUNCH_CHECKLIST.md) · [MVP_DECLARATION_MVP.md](MVP_DECLARATION_MVP.md) · [ATTESTATION_PACK_MVP.md](ATTESTATION_PACK_MVP.md) · [STAGE_33_PLAN.md](STAGE_33_PLAN.md)

This is the **MVP first-tenant onboarding packaging surface**: a consolidated checklist for bringing the first commercial tenant live, extending Stage 32 H1 operator handoff and LAUNCH honesty. It indexes environment readiness, no-demo policy, admin registration, RBAC smoke, API key, in-app onboarding checklist (Stage 6 N2), ERP smoke, LAUNCH §§1–3, ops take-over, and §7 Remaining — it does **not** claim live onboarding success or that the first tenant is onboarded Complete.

## Classification

| Status | Meaning |
|--------|---------|
| `packaged` | Checklist step indexed to Complete (MVP) packaging / product surfaces |
| `remaining` | Operator action in target env still required before step can complete |

Every step keeps `done: false`. Top-level `first_tenant_onboarded_claimed: false` / `live_onboarding_success_claimed: false`.

## Register scope

1. Target environment secrets / connectivity out-of-band (extends handoff phase 3).
2. No demo tenants / seed passwords / hard-coded production credentials.
3. First real company admin registration + email verification.
4. RBAC / tenant isolation smoke.
5. Tenant API key path with secret out-of-band.
6. In-app onboarding checklist (Stage 6 N2) for new tenants.
7. Core ERP smoke with real tenant data (not demo seed).
8. LAUNCH §§1–3 walk in target env Remaining.
9. Ops take-over runbooks for first-tenant support.
10. LAUNCH §7 Name/Date Remaining until real verification.

## Automation hooks

1. Maintain `ops/mvp/first-tenant-onboarding.json` (synced by `test_first_tenant_onboarding_f1.py`).
2. Align honesty with operator handoff / Remaining / declaration / LAUNCH checklist.
3. CI proves packaging honesty only — never forges live onboarding success.

## Explicitly not claimed

- First commercial tenant onboarded because Stage 33 F1 packaging exists
- Live onboarding success / demo tenant as Complete
- Live go-live / §7 / attestation Complete
- Re-packaging Stage 26–32 packs as new Complete

## Sign-off

Stage 33 F1 is met when this doc + register JSON + evidence JSON exist, `test_first_tenant_onboarding_f1.py` passes, and LAUNCH_CHECKLIST / PRODUCTION_READINESS / plan / roadmap cite Stage 33 F1 without inventing live onboarding success.

See also Stage 194 first-tenant live onboarding remaining-gate index: [`FIRST_TENANT_LIVE_ONBOARDING_REMAINING_GATE_MVP.md`](FIRST_TENANT_LIVE_ONBOARDING_REMAINING_GATE_MVP.md).
