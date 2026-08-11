# Stage 36 Plan — Commercial Assurance Completion Fidelity

**Status:** Open — S1 next (ADR-077)  
**Base:** Support SLA Boundary Pack + Billing-Deferred Honesty Pack → Commercial Assurance Completion Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-077](ADR_077_STAGE36_OPEN.md)

Stage 36 opens after Stage 35 freeze: **Support SLA / Incident Escalation Boundary Packaging + Billing-Deferred Commercial Honesty Packaging → Commercial Assurance Completion Fidelity**. These workstreams were **owner-deferred** from Stage 34 when Stage 35 E2E operational smoke was prioritized. This track packages the remaining customer/procurement-facing assurance surfaces on proven Stage 30 support / Stage 34 assurance / ADR-002 assets — **not** claiming live support SLA Complete, paid billing Complete, hosted PagerDuty/helpdesk SaaS Complete, live go-live / §7, SOC 2 / ISO Complete, re-packaging Stage 26–35 packs as new Complete, or reopening Stages 1–35 frozen feature scopes (except explicitly completing the deferred S1/B1 packaging scopes in this plan).

## Product outline (owner)

```
Support SLA Boundary Pack
        +
Billing-Deferred Honesty Pack
        ↓
Commercial Assurance Completion Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 30 S1 support runbook / Stage 34 A1–C1 / ADR-002 honesty patterns — do not invent fake live SLA, paid billing, or go-live success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–35 feature scopes beyond the deferred S1/B1 packaging named here. Main `ci.yml` stays deploy-free (**Stage 18 C1**); operator templates stay separate.
6. Deferred ADRs (001–006) stay deferred unless explicitly in this plan (billing honesty packaging only — not implementing paid billing).
7. Do not re-ship Stage 26–35 packs as new Complete — index / extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | Support SLA / incident escalation boundary packaging | P0 | PENDING |
| **B1** | Billing-deferred commercial honesty packaging (not paid billing Complete) | P0 | PENDING |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | PENDING |
| **H36x** | Stage 36 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Paid billing provider / checkout / charge Complete (ADR-002 remains deferred implementation)
- Schema-per-tenant (ADR-001); i18n packs (ADR-006); ADR-005 store membership; hard-delete archival (ADR-003)
- Open Banking; tax e-file portals
- Claiming hosted Grafana/PagerDuty/SIEM / helpdesk as SaaS Complete
- Claiming live support SLA / on-call rota / incident drill Complete
- Forged production LAUNCH §7 / go-live attestation Complete
- Claiming SOC 2 / ISO certification Complete
- Re-packaging Stage 26–35 packs as new Complete
- Live E2E smoke executed Complete (Stage 35 packaging remains packaging-only)
- Live production cutover via main `ci.yml` deploy jobs
- External LLM / Prophet; PO OCR auto-apply
- Reopening Stages 1–35 frozen feature scopes (except deferred S1/B1 packaging completion)

## S1 acceptance criteria

- [ ] Support SLA / incident escalation boundary packaging consolidating Stage 30 support / incident packs into a customer-facing SLA honesty boundary (not forging live SLA / PagerDuty Complete).
- [ ] Automated proof: `backend/tests/test_support_sla_boundary_s1.py`.
- [ ] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [ ] Plan / launch / roadmap cite Stage 36 S1.

## B1 acceptance criteria

- [ ] Billing-deferred commercial honesty packaging indexing ADR-002 / plan_code metadata honesty for procurement (not claiming paid billing Complete).
- [ ] Automated proof: `backend/tests/test_billing_deferred_honesty_b1.py`.
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP honesty updated.
- [ ] Plan / launch / roadmap cite Stage 36 B1.

## D1 acceptance criteria

- [ ] `docs/STAGE_36_FIDELITY.md` maps S1–B1 evidence → readiness / launch / deploy / security docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 36 D1.
- [ ] Automated proof: `backend/tests/test_stage36_fidelity_d1.py`.

## H36x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for S1–D1 / H36x — `docs/STAGE_36_EXIT_CRITERIA.md`.
- [ ] Scope freeze ADR accepted — `docs/ADR_078_STAGE36_FREEZE.md` (number reserved at close).
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / PRODUCTION_READINESS cite exit + freeze.
- [ ] Automated proof: `backend/tests/test_stage36_exit_h36x.py`.
- [ ] Stages 1–35 freezes remain; Stage 37+ requires explicit open ADR after CONTINUE/NEXT.

## Sign-off

Stage 36 open under ADR-077. S1 next. Stages 1–35 remain frozen for their scopes (Stage 34 S1/B1 packaging scopes reopen only inside this plan).
