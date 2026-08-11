# ADR-061: Stage 28 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-11  
**Supersedes (in part):** ADR-060 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 27 Commercial MVP Release Fidelity exit criteria are met (`docs/STAGE_27_EXIT_CRITERIA.md`) and Stage 27 feature scope remains frozen (ADR-060). Product owner approved opening Stage 28 after Stage 27 freeze via CONTINUE/NEXT with a distinct product outline: Operator PITR Drill Pack + Staging GHA Deploy Workflow + Grafana/Alertmanager Packaging + Operator 1000-VU Cert Pack → Staging Certification Fidelity. Stages 26–27 closed ops-platform and release packaging as Complete (MVP) with honest Remaining for live staging drills, staging-only deploy workflows, hosted observability packaging, and ~1000-VU certificates. Remaining gap is staging-certification packaging on proven Stage 26/27 assets — **not** paid billing, schema-per-tenant, i18n packs, Open Banking, tax e-file, ADR-003/005 feature builds, vendor pen-test purchase, forged production sign-off, external LLM/Prophet, or reopening Stages 1–27.

```
Operator PITR Drill Pack
        +
Staging GHA Deploy Workflow
        +
Grafana / Alertmanager Packaging
        +
Operator 1000-VU Cert Pack
        ↓
Staging Certification Fidelity
```

## Decision

1. **Stage 28 delivery track is open** per `docs/STAGE_28_PLAN.md` (Staging Certification Fidelity).
2. **Stage 1–27 freezes remain** for their respective scopes: bugfixes / security / tests / docs only.
3. Deliver Stage 28 **one workstream at a time** (R1 → G1 → A1 → C1 → D1 → H28x) with tests, commit, push, and PR update after each feature.
4. Explicitly out of this pass: paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006); ADR-005 store membership; hard-delete archival (ADR-003); Open Banking; tax e-file portals; claiming hosted Grafana/PagerDuty as SaaS Complete; live production cutover via main `ci.yml`; vendor-purchased pen test; forged LAUNCH §7; multi-bin; FIFO/LIFO/WA; external LLM / Prophet; PO OCR auto-apply; reopening Stages 1–27 frozen feature scopes.
5. Main `ci.yml` remains deploy-free (**Stage 18 C1**); staging GHA templates stay outside main CI.

## Consequences

- Agents may implement Stage 28 plan items without reopening Stage 1–27 feature scope.
- Stage 28 exit requires `docs/STAGE_28_EXIT_CRITERIA.md` (created at close) with no CRITICAL/MISSING rows for planned workstreams.
