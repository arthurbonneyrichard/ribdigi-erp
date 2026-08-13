# Production Cutover Pack MVP — Operator Go-Live Harness

**Status:** Complete (MVP) — Stage 29 X1  
**Evidence:** `backend/tests/test_cutover_pack_x1.py` · `/opt/cursor/artifacts/launch/stage29_x1_cutover_pack.json`  
**Checklist map:** `ops/launch/cutover-checklist.json`  
**Evidence schema:** `ops/launch/cutover-evidence.example.json`  
**GHA template:** `ops/k8s/deploy-production.example.yml`  
**Related:** [LAUNCH_CERT_MVP.md](LAUNCH_CERT_MVP.md) (Stage 27 L1) · [STAGING_GHA_MVP.md](STAGING_GHA_MVP.md) (Stage 28 G1) · `docs/LAUNCH_CHECKLIST.md`

This is the **MVP production cutover packaging surface**: cutover / rollback / secrets-handoff checklist mapping LAUNCH §§1–3 / §7, plus an optional production GHA template extending Stage 28 G1. It is **not** a forged §7 Name/Date sign-off and does **not** claim live production cutover already happened.

## Classification

| Class | Meaning |
|-------|---------|
| `operator_required` | Walk §§1–3 in the real env, hand off secrets, promote, smoke, fill §7 only after success |
| `ci_proven` | Stage 27 L1 checklist map + Stage 28 G1 staging template honesty + this pack |
| `deferred` | Live production cutover Complete; forged §7; production deploy jobs in main `ci.yml` |

## LAUNCH section map

| Cutover phase | Maps to | Notes |
|---------------|---------|-------|
| Pre-flight config / secrets / identity / integrations | §§1–3 | Stay `[ ]` until verified in target env |
| Secrets handoff | §1 | Out-of-band secret store; never commit kubeconfig / JWT / DB URLs |
| Promote + smoke | Stage 28 G1 → production template | Prefer `deploy-production.example.yml` copy, not main `ci.yml` |
| Rollback | Ops change-log | Helm revision rollback / previous image tag; record outcome |
| Sign-off | §7 | Empty Name/Date until Engineering / Operations / Product sign |

## Automation hooks

1. Maintain `ops/launch/cutover-checklist.json` (synced by `test_cutover_pack_x1.py`).
2. Keep `ops/k8s/deploy-production.example.yml` **outside** main `.github/workflows/ci.yml` (Stage 18 C1).
3. Operators copy `cutover-evidence.example.json` after a real cutover — packaging evidence keeps `production_cutover_claimed: false`, `section_7_signed: false`.

## Explicitly not claimed

- Filling §7 Name/Date as if production already signed
- Checking §§1–3 because Stage 29 X1 packaging exists
- Wiring production `helm upgrade` / `kubectl` into main `ci.yml`
- Treating Stage 27 L1 / Stage 28 G1 / Stage 29 X1 Complete as “production is live”

## Sign-off

Stage 29 X1 is met when this doc + checklist + evidence schema + production GHA template + evidence JSON exist, `test_cutover_pack_x1.py` passes, and LAUNCH_CHECKLIST / PRODUCTION_READINESS / launch / roadmap cite Stage 29 X1 without inventing live cutover or forged §7.

See also Stage 202 Tenant MVP Production Launch remaining-gate index fidelity (`docs/PRODUCTION_LAUNCH_REMAINING_GATE_MVP.md`, ADR-410 / ADR-411).

See also Stage 203 Tenant MVP Cutover remaining-gate index fidelity (`docs/CUTOVER_REMAINING_GATE_MVP.md`, ADR-412 / ADR-413).
