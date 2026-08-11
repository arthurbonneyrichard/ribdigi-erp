# Stage 40 Plan — Commercial Availability & Supply-Chain Fidelity

**Status:** Open — U1 complete; S1 next  
**Base:** Status Page / Uptime Honesty Pack + SBOM / Dependency Disclosure Honesty Pack → Commercial Availability & Supply-Chain Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-085](ADR_085_STAGE40_OPEN.md)  
**Prior freeze:** [ADR-084](ADR_084_STAGE39_FREEZE.md) · [STAGE_39_EXIT_CRITERIA.md](STAGE_39_EXIT_CRITERIA.md)

Stage 40 opens after Stage 39 freeze: **Status Page / Uptime Honesty Packaging + SBOM / Dependency Disclosure Honesty Packaging → Commercial Availability & Supply-Chain Fidelity**. PRODUCT_OVERVIEW uptime themes, Stage 30–36 support / incident Remaining (status-page), and SECURITY_GUIDE §12.4 dependency / SBOM aspirational language lack dedicated customer-facing honesty packs. This track packages those Remaining surfaces on proven Stage 27–30 monitoring / incident / support and Stage 38–39 disclosure / contract assets — **not** claiming a live public status page Complete, measured 99.9% uptime SLA Complete, live SBOM pipeline / signed image releases Complete, live go-live / §7, SOC 2 / ISO Complete, re-packaging Stage 26–39 packs as new Complete, or reopening Stages 1–39 frozen feature scopes.

## Product outline (owner)

```
Status Page / Uptime Honesty Pack
        +
SBOM / Dependency Disclosure Honesty Pack
        ↓
Commercial Availability & Supply-Chain Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 27–30 ops / Stage 36 support / SECURITY_GUIDE honesty patterns — do not invent fake status-page or SBOM pipeline success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–39 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**); operator templates stay separate.
6. Deferred ADRs (001–006) stay deferred unless explicitly in this plan.
7. Do not re-ship Stage 26–39 packs as new Complete — index / extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **U1** | Status page / uptime honesty packaging (not live status page / 99.9% SLA Complete) | P0 | COMPLETE |
| **S1** | SBOM / dependency disclosure honesty packaging (not live SBOM pipeline Complete) | P0 | PENDING |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | PENDING |
| **H40x** | Stage 40 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Live public status page / customer uptime dashboard Complete
- Measured 99.9% uptime SLA / availability guarantee Complete
- Live SBOM generation / Cosign image signing / FOSSA license SaaS Complete
- Paid Dependabot / Snyk continuous scanning SaaS Complete
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
- Re-packaging Stage 26–39 packs as new Complete
- Live production cutover via main `ci.yml` deploy jobs
- External LLM / Prophet; PO OCR auto-apply
- Reopening Stages 1–39 frozen feature scopes

## U1 acceptance criteria

- [x] Status page / uptime honesty packaging consolidating PRODUCT_OVERVIEW uptime theme and Stage 30–36 support Remaining (status-page) into a customer-facing availability boundary (not forging live status page / 99.9% SLA Complete).
- [x] Automated proof: `backend/tests/test_status_uptime_u1.py`.
- [x] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [x] Plan / launch / roadmap cite Stage 40 U1.

## S1 acceptance criteria

- [ ] SBOM / dependency disclosure honesty packaging indexing SECURITY_GUIDE §12.4 SBOM / vulnerability-scanning themes (not claiming live SBOM pipeline / Cosign signing Complete).
- [ ] Automated proof: `backend/tests/test_sbom_disclosure_s1.py`.
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP honesty updated.
- [ ] Plan / launch / roadmap cite Stage 40 S1.

## D1 acceptance criteria

- [ ] `docs/STAGE_40_FIDELITY.md` maps U1–S1 evidence → readiness / launch / deploy / security docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 40 D1.
- [ ] Automated proof: `backend/tests/test_stage40_fidelity_d1.py`.

## H40x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for U1–D1 / H40x — `docs/STAGE_40_EXIT_CRITERIA.md`.
- [ ] Freeze ADR accepted — `docs/ADR_086_STAGE40_FREEZE.md` (planned id).
- [ ] Automated proof: `backend/tests/test_stage40_exit_h40x.py`.
