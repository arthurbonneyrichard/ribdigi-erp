# Stage 49 Plan — Commercial Channel & Pricing Fidelity

**Status:** Open — R1 next  
**Base:** Partner / Reseller Terms Honesty Pack + Pricing Transparency Honesty Pack → Commercial Channel & Pricing Fidelity  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-103](ADR_103_STAGE49_OPEN.md)  
**Prior freeze:** [ADR-102](ADR_102_STAGE48_FREEZE.md) · [STAGE_48_EXIT_CRITERIA.md](STAGE_48_EXIT_CRITERIA.md)

Stage 49 opens after Stage 48 freeze: **Partner / Reseller Terms Honesty Packaging + Pricing Transparency Honesty Packaging → Commercial Channel & Pricing Fidelity**. PRODUCT_OVERVIEW white-label / reseller and transparent published pricing themes, plus Stage 36 billing-deferred and Stage 43/39 ToS/MSA adjacency, lack dedicated customer-facing honesty packs for partner / reseller / white-label boundaries and published edition price-list transparency Remaining. This track packages those Remaining surfaces on proven Stage 36–48 commercial / billing-deferred / legal assets — **not** claiming live partner program Complete, signed reseller agreement Complete, white-label live Complete, public pricing portal Complete, checkout pricing Complete, paid billing Complete, live go-live / §7, SOC 2 / ISO Complete, re-packaging Stage 26–48 packs as new Complete, or reopening Stages 1–48 frozen feature scopes.

## Product outline (owner)

```
Partner / Reseller Terms Honesty Pack
        +
Pricing Transparency Honesty Pack
        ↓
Commercial Channel & Pricing Fidelity
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven Stage 36 billing-deferred / Stage 43 ToS / Stage 39 MSA / PRODUCT_OVERVIEW honesty patterns — do not invent fake live partner programs or public pricing-portal success.
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–48 feature scopes. Main `ci.yml` stays deploy-free (**Stage 18 C1**); operator templates stay separate.
6. Deferred ADRs (001–006) stay deferred unless explicitly in this plan (ADR-002 billing remains deferred).
7. Do not re-ship Stage 26–48 packs as new Complete — index / extend adjacent Remaining only.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **R1** | Partner / reseller / white-label terms honesty packaging (not live partner program / signed reseller Complete) | P0 | PENDING |
| **L1** | Pricing transparency / published edition price-list honesty packaging (not public pricing portal / checkout pricing Complete) | P0 | PENDING |
| **D1** | Spec / readiness / launch / deploy / security fidelity sync | P1 | PENDING |
| **H49x** | Stage 49 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Live partner program / signed reseller agreement / white-label Complete
- Public pricing portal / binding list prices / checkout pricing Complete
- Paid billing / payment-provider Complete (ADR-002)
- Signed SOW / live professional-services delivery Complete
- Live customer training / attendance certification Complete
- Issued COI / live cyber policy / customer audit executed Complete
- Signed liability-cap / indemnity / legal-counsel Complete
- Live service credits / warranty Complete
- Measured RTO / RPO SLA / multi-region failover Complete
- Customer data-return / offboarding portal Complete
- Multi-region / per-market data residency Complete
- HSM / live Vault / customer-managed keys Complete
- Signed customer ToS / AUP / cookie-consent / CMP Complete
- Signed customer DPA / MSA / contract execution Complete
- External LLM / Prophet / AI certification Complete
- WCAG 2.1 AA audit / live accessibility conformance Complete
- Public change calendar / maintenance portal Complete
- Live public status page / measured 99.9% uptime SLA Complete
- Live SBOM generation / Cosign image signing Complete
- Schema-per-tenant (ADR-001); i18n packs (ADR-006)
- User↔store membership (ADR-005); hard-delete archival (ADR-003)
- Open Banking; tax e-file portals
- Claiming hosted Grafana/PagerDuty/SIEM / helpdesk as SaaS Complete
- Claiming live vulnerability disclosure / breach drill Complete
- Forged production LAUNCH §7 / go-live attestation Complete
- Claiming SOC 2 / ISO certification Complete
- Re-packaging Stage 26–48 packs as new Complete
- Live production cutover via main `ci.yml` deploy jobs
- External LLM / Prophet; PO OCR auto-apply
- Reopening Stages 1–48 frozen feature scopes

## R1 acceptance criteria

- [ ] Partner / reseller / white-label terms honesty packaging consolidating PRODUCT_OVERVIEW channel themes and Stage 43 ToS / Stage 39 MSA adjacency (not forging live partner program / signed reseller Complete).
- [ ] Automated proof: `backend/tests/test_partner_reseller_r1.py`.
- [ ] LAUNCH_CHECKLIST / PRODUCTION_READINESS honesty updated.
- [ ] Plan / launch / roadmap cite Stage 49 R1.

## L1 acceptance criteria

- [ ] Pricing transparency honesty packaging indexing PRODUCT_OVERVIEW edition prices and Stage 36 billing-deferred adjacency (not claiming public pricing portal / checkout pricing Complete).
- [ ] Automated proof: `backend/tests/test_pricing_transparency_l1.py`.
- [ ] LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP honesty updated.
- [ ] Plan / launch / roadmap cite Stage 49 L1.

## D1 acceptance criteria

- [ ] `docs/STAGE_49_FIDELITY.md` maps R1–L1 evidence → readiness / launch / deploy / security docs.
- [ ] PRODUCTION_READINESS / LAUNCH_CHECKLIST / DEVELOPMENT_ROADMAP / DEPLOYMENT_GUIDE / SECURITY_GUIDE cite Stage 49 D1.
- [ ] Automated proof: `backend/tests/test_stage49_fidelity_d1.py`.

## H49x acceptance criteria

- [ ] Exit criteria document with no CRITICAL/MISSING rows for R1–D1 / H49x — `docs/STAGE_49_EXIT_CRITERIA.md`.
- [ ] Freeze ADR accepted — `docs/ADR_104_STAGE49_FREEZE.md` (planned id).
- [ ] Automated proof: `backend/tests/test_stage49_exit_h49x.py`.
