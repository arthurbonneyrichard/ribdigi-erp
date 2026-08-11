# Stage 41 Plan — Commercial Accessibility & Change Governance Fidelity

**Status:** Open — D1 complete; H41x next  
**Base:** Accessibility Statement Honesty Pack + Change / Maintenance Governance Honesty Pack → Commercial Accessibility & Change Governance Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-087](ADR_087_STAGE41_OPEN.md)  
**Prior freeze:** [ADR-086](ADR_086_STAGE40_FREEZE.md) · [STAGE_40_EXIT_CRITERIA.md](STAGE_40_EXIT_CRITERIA.md)

Stage 41 opens after Stage 40 freeze: **Accessibility Statement Honesty Packaging + Change / Maintenance Governance Honesty Packaging → Commercial Accessibility & Change Governance Fidelity**. BR WCAG 2.1 AA themes, DEVELOPMENT_ROADMAP unchecked accessibility, and operator maintenance-window language (ADMIN_MANUAL / DR restore) lack dedicated customer-facing honesty packs. This track packages those Remaining surfaces on proven Stage 32 handoff / Stage 36 support / Stage 40 availability assets — **not** claiming WCAG 2.1 AA audit Complete, live accessibility conformance Complete, a public change calendar Complete, live go-live / §7, SOC 2 / ISO Complete, re-packaging Stage 26–40 packs as new Complete, or reopening Stages 1–40 frozen feature scopes.

## Product outline (owner)

```
Accessibility Statement Honesty Pack
        +
Change / Maintenance Governance Honesty Pack
        ↓
Commercial Accessibility & Change Governance Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 32–36 handoff / support and Stage 40 availability honesty patterns — do not invent fake WCAG audits or public change calendars.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–40 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**); operator templates stay separate.
6. Deferred ADRs (001–006) stay deferred unless explicitly in this plan.
7. Do not re-ship Stage 26–40 packs as new Complete — index / extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **A1** | Accessibility statement honesty packaging (not WCAG AA audit Complete) | P0 | COMPLETE |
| **C1** | Change / maintenance governance honesty packaging (not public change calendar Complete) | P0 | COMPLETE |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | COMPLETE |
| **H41x** | Stage 41 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- WCAG 2.1 AA audit / certification Complete
- Live accessibility conformance / remediation program Complete
- Public change calendar / maintenance portal Complete
- Live public status page / measured 99.9% uptime SLA Complete
- Live SBOM generation / Cosign image signing Complete
- Signed customer DPA / MSA / contract execution Complete
- Legal counsel / outside counsel approval Complete
- GDPR / privacy certification Complete
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete archival (ADR-003)
- Open Banking; tax e-file portals
- Claiming hosted Grafana/PagerDuty/SIEM / helpdesk as SaaS Complete
- Claiming live vulnerability disclosure / breach drill Complete
- Forged production LAUNCH §7 / go-live attestation Complete
- Claiming SOC 2 / ISO certification Complete
- Re-packaging Stage 26–40 packs as new Complete
- Live production cutover via main `ci.yml` deploy jobs
- External LLM / Prophet; PO OCR auto-apply
- Reopening Stages 1–40 frozen feature scopes

## A1 acceptance criteria

- [x] Accessibility statement honesty packaging consolidating BR WCAG 2.1 AA theme and DEVELOPMENT_ROADMAP unchecked accessibility into a customer-facing accessibility boundary (not forging WCAG AA audit Complete).
- [x] Automated proof: `backend/tests/test_accessibility_statement_a1.py`.
- [x] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [x] Plan / launch / roadmap cite Stage 41 A1.

## C1 acceptance criteria

- [x] Change / maintenance governance honesty packaging indexing ADMIN_MANUAL / DR maintenance-window themes (not claiming public change calendar Complete).
- [x] Automated proof: `backend/tests/test_change_governance_c1.py`.
- [x] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP honesty updated.
- [x] Plan / launch / roadmap cite Stage 41 C1.

## D1 acceptance criteria

- [x] `docs/STAGE_41_FIDELITY.md` maps A1–C1 evidence → readiness / launch / deploy / security docs.
- [x] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 41 D1.
- [x] Automated proof: `backend/tests/test_stage41_fidelity_d1.py`.

## H41x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for A1–D1 / H41x — `docs/STAGE_41_EXIT_CRITERIA.md`.
- [ ] Freeze ADR accepted — `docs/ADR_088_STAGE41_FREEZE.md` (planned id).
- [ ] Automated proof: `backend/tests/test_stage41_exit_h41x.py`.
