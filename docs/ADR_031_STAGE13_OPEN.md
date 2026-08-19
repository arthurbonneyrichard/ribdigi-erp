# ADR-031: Stage 13 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-10  
**Supersedes (in part):** ADR-030 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 12 Order-to-Cash & POS Chain Fidelity exit criteria are met (`docs/STAGE_12_EXIT_CRITERIA.md`) and Stage 12 feature scope remains frozen (ADR-030). Product owner approved opening Stage 13 after Stage 12 freeze by specifying the target pipeline:

POS → Sale → Payment → Inventory Deduction → Receipt → Accounting → Audit

Stage 12 already delivered cash-path POS E2E and domain audits. Remaining commercial-MVP gaps on this chain are atomic sale integrity under stock failure, multi-tender closeout with receipt send and cash-portion drawer, and fidelity sync. Greenfield Kubernetes, WAL/PITR, vendor pen test, Open Banking, FIFO/LIFO, and USB/serial drivers remain deferred.

## Decision

1. **Stage 13 delivery track is open** per `docs/STAGE_13_PLAN.md`.
2. **Stage 1–12 freezes remain** for their respective scopes: bugfixes / security / tests / docs only.
3. Deliver Stage 13 **one workstream at a time** (H1 → H2 → D1 → H13x) with tests, commit, push, and PR update after each feature.
4. Explicitly out of this pass: Kubernetes/Helm, full Prometheus/Grafana stack, pg_dump/WAL/S3 PITR, vendor penetration test, paid billing (ADR-002), schema-per-tenant (ADR-001), i18n packs (ADR-006), certified 1000-VU ops run, Prophet/LLM, multi-bin, PO Kanban, Open Banking, tax e-file, FIFO/LIFO/WA, USB/serial POS drivers beyond existing bridges, user↔store membership (ADR-005).

## Consequences

- Agents may implement Stage 13 plan items without reopening Stage 1–12 feature scope.
- Stage 13 exit requires `docs/STAGE_13_EXIT_CRITERIA.md` (created at close) with no CRITICAL/MISSING rows for planned workstreams.

## Closure (2026-08-10)

Stage 13 workstreams H1, H2, D1, H13x met exit criteria (`docs/STAGE_13_EXIT_CRITERIA.md`). Feature scope is frozen under [ADR-032](ADR_032_STAGE13_FREEZE.md). This open ADR remains historical; new Stage 13 feature work is not permitted except bugfixes / security / tests / docs.
