# Stage 46 Plan — Commercial Liability & Remedy Fidelity

**Status:** Open — L1 next  
**Base:** Limitation of Liability / Indemnity Honesty Pack + Service Credit / Warranty Honesty Pack → Commercial Liability & Remedy Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-097](ADR_097_STAGE46_OPEN.md)  
**Prior freeze:** [ADR-096](ADR_096_STAGE45_FREEZE.md) · [STAGE_45_EXIT_CRITERIA.md](STAGE_45_EXIT_CRITERIA.md)

Stage 46 opens after Stage 45 freeze: **Limitation of Liability / Indemnity Honesty Packaging + Service Credit / Warranty Honesty Packaging → Commercial Liability & Remedy Fidelity**. Stage 39 MSA security-addendum and Stage 43 ToS/AUP notice packs, plus Stage 36 support-SLA and Stage 40 uptime / Stage 45 RTO adjacency, lack dedicated customer-facing honesty packs for liability / indemnity boundaries and service-credit / warranty remedy Remaining. This track packages those Remaining surfaces on proven Stage 36–45 commercial / contract / availability assets — **not** claiming signed liability caps Complete, live indemnity Complete, live service credits Complete, warranty Complete, live go-live / §7, SOC 2 / ISO Complete, re-packaging Stage 26–45 packs as new Complete, or reopening Stages 1–45 frozen feature scopes.

## Product outline (owner)

```
Limitation of Liability / Indemnity Honesty Pack
        +
Service Credit / Warranty Honesty Pack
        ↓
Commercial Liability & Remedy Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 36–45 support-SLA / MSA / ToS / uptime / RTO honesty patterns — do not invent fake signed liability caps or live service-credit success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–45 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**); operator templates stay separate.
6. Deferred ADRs (001–006) stay deferred unless explicitly in this plan.
7. Do not re-ship Stage 26–45 packs as new Complete — index / extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **L1** | Limitation of liability / indemnity honesty packaging (not signed liability-cap / indemnity Complete) | P0 | PENDING |
| **W1** | Service credit / warranty honesty packaging (not live service credits / warranty Complete) | P0 | PENDING |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | PENDING |
| **H46x** | Stage 46 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Signed liability-cap / indemnity / legal-counsel Complete
- Live service credits / warranty Complete
- Measured RTO / RPO SLA / multi-region failover Complete
- Customer data-return / offboarding portal Complete
- Hot audit-row physical purge Complete
- Multi-region / per-market data residency Complete
- HSM / live Vault / customer-managed keys Complete
- Signed customer ToS / AUP / cookie-consent / CMP Complete
- Signed customer DPA / MSA / contract execution Complete
- External LLM / Prophet / AI certification Complete
- WCAG 2.1 AA audit / live accessibility conformance Complete
- Public change calendar / maintenance portal Complete
- Live public status page / measured 99.9% uptime SLA Complete
- Live SBOM generation / Cosign image signing Complete
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete archival (ADR-003)
- Open Banking; tax e-file portals
- Claiming hosted Grafana/PagerDuty/SIEM / helpdesk as SaaS Complete
- Claiming live vulnerability disclosure / breach drill Complete
- Forged production LAUNCH §7 / go-live attestation Complete
- Claiming SOC 2 / ISO certification Complete
- Re-packaging Stage 26–45 packs as new Complete
- Live production cutover via main `ci.yml` deploy jobs
- External LLM / Prophet; PO OCR auto-apply
- Reopening Stages 1–45 frozen feature scopes

## L1 acceptance criteria

- [ ] Limitation of liability / indemnity honesty packaging consolidating Stage 39 MSA / Stage 43 ToS adjacency (not forging signed liability-cap / indemnity Complete).
- [ ] Automated proof: `backend/tests/test_liability_indemnity_l1.py`.
- [ ] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [ ] Plan / launch / roadmap cite Stage 46 L1.

## W1 acceptance criteria

- [ ] Service credit / warranty honesty packaging indexing Stage 36 support-SLA and Stage 40 uptime / Stage 45 RTO adjacency (not claiming live service credits / warranty Complete).
- [ ] Automated proof: `backend/tests/test_service_credit_warranty_w1.py`.
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP honesty updated.
- [ ] Plan / launch / roadmap cite Stage 46 W1.

## D1 acceptance criteria

- [ ] `docs/STAGE_46_FIDELITY.md` maps L1–W1 evidence → readiness / launch / deploy / security docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 46 D1.
- [ ] Automated proof: `backend/tests/test_stage46_fidelity_d1.py`.

## H46x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for L1–D1 / H46x — `docs/STAGE_46_EXIT_CRITERIA.md`.
- [ ] Freeze ADR accepted — `docs/ADR_098_STAGE46_FREEZE.md` (planned id).
- [ ] Automated proof: `backend/tests/test_stage46_exit_h46x.py`.
