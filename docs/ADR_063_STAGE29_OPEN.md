# ADR-063: Stage 29 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-062 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 28 Staging Certification Fidelity exit criteria are met (`docs/STAGE_28_EXIT_CRITERIA.md`) and Stage 28 feature scope remains frozen (ADR-062). Product owner approved opening Stage 29 after Stage 28 freeze via CONTINUE/NEXT with a distinct product outline: Vendor Pen-Test / ZAP Staging Pack + PgBouncer Soak / Helm Pooler Pack + Cert-manager / TLS Ingress Pack + Production Cutover Pack → Operator Hardening & Production Cutover Fidelity. Stages 26–28 closed ops-platform, release, and staging-certification packaging as Complete (MVP) with honest Remaining for purchased vendor pen tests, live PgBouncer soak / in-cluster pooler, cert-manager TLS cutover, and unsigned LAUNCH §§1–3 / §7. Remaining gap is adjacent operator-hardening packaging on proven Stage 26/27/28 assets — **not** paid billing, schema-per-tenant, i18n packs, Open Banking, tax e-file, ADR-003/005 feature builds, re-packaging Stage 28 R1/G1/A1/C1 packs, forging live PITR/1000-VU/GHA apply success, hosted Grafana-as-SaaS Complete, external LLM/Prophet, or reopening Stages 1–28.

```
Vendor Pen-Test / ZAP Staging Pack
        +
PgBouncer Soak / Helm Pooler Pack
        +
Cert-manager / TLS Ingress Pack
        +
Production Cutover Pack
        ↓
Operator Hardening & Cutover Fidelity
```

## Decision

1. **Stage 29 delivery track is open** per `docs/STAGE_29_PLAN.md` (Operator Hardening & Production Cutover Fidelity).
2. **Stage 1–28 freezes remain** for their respective scopes: bugfixes / security / tests / docs only.
3. Deliver Stage 29 **one workstream at a time** (V1 → B2 → T1 → X1 → D1 → H29x) with tests, commit, push, and PR update after each feature.
4. Explicitly out of this pass: paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006); ADR-005 store membership; hard-delete archival (ADR-003); Open Banking; tax e-file portals; claiming hosted Grafana/PagerDuty as SaaS Complete; live production cutover via main `ci.yml`; purchased vendor pen-test certificate as Complete; forged LAUNCH §7; re-packaging Stage 28 PITR/GHA/Grafana/1000-VU packs; forging live PITR/1000-VU/GHA apply; multi-bin; FIFO/LIFO/WA; external LLM / Prophet; PO OCR auto-apply; reopening Stages 1–28 frozen feature scopes.
5. Main `ci.yml` remains deploy-free (**Stage 18 C1**); pen-test / staging / cutover templates stay outside main CI.

## Consequences

- Agents may implement Stage 29 plan items without reopening Stage 1–28 feature scope.
- Stage 29 exit requires `docs/STAGE_29_EXIT_CRITERIA.md` (created at close) with no CRITICAL/MISSING rows for planned workstreams.
