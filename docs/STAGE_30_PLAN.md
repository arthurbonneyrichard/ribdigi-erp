# Stage 30 Plan — Go-Live Support Fidelity

**Status:** Open — L1 next (ADR-065)  
**Base:** Operator Evidence Ledger Pack + Incident Response / On-Call Pack + Support & Admin Runbook Fidelity + Go-Live Attestation Matrix Pack → Go-Live Support Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-065](ADR_065_STAGE30_OPEN.md)

Stage 30 closes the owner product outline after Stage 29 freeze: **Operator Evidence Ledger Packaging + Incident Response / On-Call Packaging + Support & Admin Runbook Fidelity + Go-Live Attestation Matrix Packaging → Go-Live Support Fidelity**. Stages 26–29 delivered Complete (MVP) ops platform, release, staging-certification, and operator-hardening **packaging** with honest Remaining for live execution, purchased vendor pen tests, hosted SaaS observability, and production §7 sign-off. This track packages **go-live support** surfaces on proven Stage 26–29 assets (evidence artifacts under `/opt/cursor/artifacts/`, `ops/` checklists, `ADMIN_MANUAL.md`, `LAUNCH_CHECKLIST.md`) — **not** inventing live pen-test/soak/TLS/cutover success, re-packaging Stage 26–29 packs as new Complete, or paid billing / schema-per-tenant / i18n / ADR-003/005 / Open Banking / tax e-file / external LLM/Prophet — and **not** reopening Stages 1–29.

## Product outline (owner)

```
Operator Evidence Ledger Pack
        +
Incident Response / On-Call Pack
        +
Support & Admin Runbook Fidelity
        +
Go-Live Attestation Matrix Pack
        ↓
Go-Live Support Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 26–29 ops patterns — do not invent fake live execution or attestation success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–29 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**); operator templates stay separate.
6. Deferred ADRs (001–006), purchased vendor pen-test certificates, and forged production sign-off stay deferred unless explicitly in this plan.
7. Do not re-ship Stage 26–29 packs as new Complete — index / extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **L1** | Operator evidence ledger (index Stage 26–29 artifacts + honesty flags) | P0 | PENDING |
| **I1** | Incident response / on-call packaging | P0 | PENDING |
| **S1** | Support & Admin runbook fidelity (ADMIN_MANUAL ↔ ops packs) | P1 | PENDING |
| **A1** | Go-live attestation matrix (Remaining honesty; not forged §7) | P1 | PENDING |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P2 | PENDING |
| **H30x** | Stage 30 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete with archival (ADR-003)
- Open Banking; tax e-file portals
- Claiming hosted Grafana/PagerDuty/SIEM as SaaS Complete
- Live production cluster cutover via main `ci.yml` deploy jobs
- Purchased vendor penetration test certificate as Complete
- Forged production LAUNCH §7 Name/Date sign-off
- Re-packaging Stage 26–29 PITR / staging GHA / Grafana / 1000-VU / pen-test / soak / TLS / cutover packs as new Complete
- Forging live PITR / 1000-VU / GHA apply / soak / ACME / cutover success
- Multi-bin; FIFO/LIFO/WA; PO Kanban polish; vendor USB/serial POS drivers
- Richer WYSIWYG template designer; restore-to-new-tenant
- External LLM / Prophet / IsolationForest; PO OCR auto-apply
- Reopening Stages 1–29 frozen feature scopes

## L1 acceptance criteria

- [ ] Operator evidence ledger packaging under `ops/launch/` or `ops/evidence/` indexing Stage 26–29 durable artifact paths + honesty flags (not claiming live runs Complete).
- [ ] Automated proof: `backend/tests/test_evidence_ledger_l1.py`.
- [ ] PRODUCTION_READINESS / launch honesty updated.
- [ ] Plan / launch / roadmap cite Stage 30 L1.

## I1 acceptance criteria

- [ ] Incident response / on-call operator packaging (checklist + runbook example — not hosted PagerDuty SaaS Complete).
- [ ] Automated proof: `backend/tests/test_incident_pack_i1.py`.
- [ ] SECURITY_GUIDE / DEPLOYMENT_GUIDE honesty updated.
- [ ] Plan / launch / roadmap cite Stage 30 I1.

## S1 acceptance criteria

- [ ] Support & Admin runbook fidelity syncing `docs/ADMIN_MANUAL.md` troubleshooting / maintenance to Stage 26–29 `ops/` packs (not inventing live ops success).
- [ ] Automated proof: `backend/tests/test_support_runbook_s1.py`.
- [ ] ADMIN_MANUAL / launch / roadmap cite Stage 30 S1.
- [ ] Plan cites Stage 30 S1.

## A1 acceptance criteria

- [ ] Go-live attestation matrix packaging mapping Remaining honesty flags across Stage 26–29 packs + LAUNCH §§1–3 / §7 (not forged attestation / §7).
- [ ] Automated proof: `backend/tests/test_attestation_pack_a1.py`.
- [ ] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [ ] Plan / launch / roadmap cite Stage 30 A1.

## D1 acceptance criteria

- [ ] `docs/STAGE_30_FIDELITY.md` maps L1–A1 evidence → readiness / launch / deploy / security / admin docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 30 D1.
- [ ] Automated proof: `backend/tests/test_stage30_fidelity_d1.py`.

## H30x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for L1–D1 / H30x — `docs/STAGE_30_EXIT_CRITERIA.md`.
- [ ] Scope freeze ADR accepted — `docs/ADR_066_STAGE30_FREEZE.md` (number reserved at close).
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS cite exit + freeze.
- [ ] Automated proof: `backend/tests/test_stage30_exit_h30x.py`.
- [ ] Stages 1–29 freezes remain; Stage 31+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 30 open under ADR-065. L1 next. Stages 1–29 remain frozen for their scopes.
