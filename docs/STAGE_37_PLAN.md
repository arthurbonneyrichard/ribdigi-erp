# Stage 37 Plan — Commercial Data Protection Fidelity

**Status:** Open — P1 next  
**Base:** Data Subject Access / Portability Pack + Erasure / Soft-Delete Honesty Pack → Commercial Data Protection Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-079](ADR_079_STAGE37_OPEN.md)  
**Freeze (prior):** [ADR-078](ADR_078_STAGE36_FREEZE.md) (Stage 36)

Stage 37 opens after Stage 36 freeze: **Data Subject Access / Portability Packaging + Erasure / Soft-Delete Honesty Packaging → Commercial Data Protection Fidelity**. BRD privacy themes (GDPR-ready access, portability, erasure) and ADR-003 soft-delete honesty are indexed in Stage 33–34 compliance surfaces but lack dedicated commercial packaging packs. This track packages those Remaining honesty surfaces on proven Stage 18 backup/export, Stage 31 deferred ADR, and ADR-003 assets — **not** claiming GDPR certification Complete, live DSAR portal Complete, hard-delete archival Complete, live go-live / §7, SOC 2 / ISO Complete, re-packaging Stage 26–36 packs as new Complete, or reopening Stages 1–36 frozen feature scopes.

## Product outline (owner)

```
Data Subject Access / Portability Pack
        +
Erasure / Soft-Delete Honesty Pack
        ↓
Commercial Data Protection Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 18 backup/export / Stage 31 R1 deferred ADR / ADR-003 / Stage 33–34 compliance honesty patterns — do not invent fake GDPR certification, live DSAR, or hard-delete success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–36 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**); operator templates stay separate.
6. Deferred ADRs (001–006) stay deferred unless explicitly in this plan (erasure honesty packaging only — not implementing ADR-003 hard-delete archival).
7. Do not re-ship Stage 26–36 packs as new Complete — index / extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **P1** | Data subject access / portability packaging (not GDPR / DSAR Complete) | P0 | PENDING |
| **E1** | Erasure / soft-delete honesty packaging (ADR-003 boundary; not hard-delete Complete) | P0 | PENDING |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | PENDING |
| **H37x** | Stage 37 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- GDPR / privacy regulation certification Complete
- Live DSAR portal / automated subject-request workflow Complete
- ADR-003 hard-delete with archival implementation (post-MVP)
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005)
- Open Banking; tax e-file portals
- Claiming hosted Grafana/PagerDuty/SIEM / helpdesk as SaaS Complete
- Claiming live support SLA / on-call rota / incident drill Complete
- Forged production LAUNCH §7 / go-live attestation Complete
- Claiming SOC 2 / ISO certification Complete
- Re-packaging Stage 26–36 packs as new Complete
- Live E2E smoke executed Complete (Stage 35 packaging remains packaging-only)
- Live production cutover via main `ci.yml` deploy jobs
- External LLM / Prophet; PO OCR auto-apply
- Reopening Stages 1–36 frozen feature scopes

## P1 acceptance criteria

- [ ] Data subject access / portability packaging consolidating existing export / backup / report surfaces into a customer-facing portability honesty boundary (not forging GDPR / live DSAR Complete).
- [ ] Automated proof: `backend/tests/test_data_portability_p1.py`.
- [ ] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [ ] Plan / launch / roadmap cite Stage 37 P1.

## E1 acceptance criteria

- [ ] Erasure / soft-delete honesty packaging indexing ADR-003 soft-delete MVP vs hard-delete archival Remaining (not claiming hard-delete Complete).
- [ ] Automated proof: `backend/tests/test_erasure_honesty_e1.py`.
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP honesty updated.
- [ ] Plan / launch / roadmap cite Stage 37 E1.

## D1 acceptance criteria

- [ ] `docs/STAGE_37_FIDELITY.md` maps P1–E1 evidence → readiness / launch / deploy / security docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 37 D1.
- [ ] Automated proof: `backend/tests/test_stage37_fidelity_d1.py`.

## H37x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for P1–D1 / H37x — `docs/STAGE_37_EXIT_CRITERIA.md`.
- [ ] Scope freeze ADR accepted — `docs/ADR_080_STAGE37_FREEZE.md`.
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS cite exit + freeze.
- [ ] Automated proof: `backend/tests/test_stage37_exit_h37x.py`.
- [ ] Stages 1–36 freezes remain; Stage 38+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 37 opens under ADR-079. P1 is next. Stages 1–36 remain frozen for their scopes.
