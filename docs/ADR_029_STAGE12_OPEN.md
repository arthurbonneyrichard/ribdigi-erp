# ADR-029: Stage 12 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-10  
**Supersedes (in part):** ADR-028 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 11 Purchase-to-Pay Chain Fidelity exit criteria are met (`docs/STAGE_11_EXIT_CRITERIA.md`) and Stage 11 feature scope remains frozen (ADR-028). Product owner approved opening Stage 12 (Order-to-Cash & POS Chain Fidelity) after Stage 11 freeze by specifying the target pipeline:

Customers → Sales → Sales Items → Invoices → Payments → POS (product search, barcode, cart, quantity, discount, tax, payment, receipt, shift/cash controls)

Remaining commercial-MVP gaps include sales line tax applied before discount (unlike POS/PO), missing Order-to-Cash and POS end-to-end automated proofs, and BR-7/8 / launch-checklist fidelity. Greenfield Kubernetes, WAL/PITR, vendor pen test, Open Banking, FIFO/LIFO, and USB serial drivers remain deferred.

## Decision

1. **Stage 12 delivery track is open** per `docs/STAGE_12_PLAN.md`.
2. **Stage 1–11 freezes remain** for their respective scopes: bugfixes / security / tests / docs only.
3. Deliver Stage 12 **one workstream at a time** (C1 → C2 → A1 → D1 → H12x) with tests, commit, push, and PR update after each feature.
4. Explicitly out of this pass: Kubernetes/Helm, full Prometheus/Grafana stack, pg_dump/WAL/S3 PITR, vendor penetration test, paid billing (ADR-002), schema-per-tenant (ADR-001), i18n packs (ADR-006), certified 1000-VU ops run, Prophet/LLM, multi-bin, PO Kanban, Open Banking, tax e-file, FIFO/LIFO/WA, USB/serial POS drivers beyond existing bridges, user↔store membership (ADR-005).

## Consequences

- Agents may implement Stage 12 plan items without reopening Stage 1–11 feature scope.
- Stage 12 exit requires `docs/STAGE_12_EXIT_CRITERIA.md` (created at close) with no CRITICAL/MISSING rows for planned workstreams.

## Closure (2026-08-10)

Stage 12 workstreams C1, C2, A1, D1, H12x met exit criteria (`docs/STAGE_12_EXIT_CRITERIA.md`). Feature scope is frozen under [ADR-030](ADR_030_STAGE12_FREEZE.md). This open ADR remains historical; new Stage 12 feature work is not permitted except bugfixes / security / tests / docs.
