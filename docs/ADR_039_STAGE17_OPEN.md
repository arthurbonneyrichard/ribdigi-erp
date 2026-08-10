# ADR-039: Stage 17 Delivery Track Opened

**Status:** Accepted  
**Date:** 2026-08-10  
**Supersedes (in part):** ADR-038 clause that blocked opening the next delivery track until explicit sign-off

## Context

Stage 16 Multi-Store / Reports / Notifications Fidelity exit criteria are met (`docs/STAGE_16_EXIT_CRITERIA.md`) and Stage 16 feature scope remains frozen (ADR-038). Product owner approved opening Stage 17 after Stage 16 freeze via CONTINUE/NEXT, targeting Inventory catalog and stock-ops fidelity on the existing Stage 2 engine:

```
Inventory
  Catalog (Categories · Brands · Units · Variants · Barcode · Images · Batch/Expiry)
  Stock Operations (Stock In · Stock Out · Adjustment · Opening Stock · Stock Count)
  Warehouse Stock (Per-location qty · Reorder levels · Inter-warehouse transfer)
  Low Stock (Traffic lights · Alerts · Purchase suggestions / reorder-PO)
```

Stage 2 already delivered advanced catalog/stock ops (I1–I6; ADR-010). Stage 9 valuation, Stage 15 sales stock-out chain, and Stage 16 transfer→warehouse proofs exist. Remaining commercial-MVP gaps are **BR-5.1–5.5 checkbox drift** and consolidated live proofs across catalog → stock ops → warehouse → low-stock — **not** greenfield Inventory, multi-bin, or FIFO/LIFO.

## Decision

1. **Stage 17 delivery track is open** per `docs/STAGE_17_PLAN.md` (Inventory Catalog & Stock Ops Fidelity).
2. **Stage 1–16 freezes remain** for their respective scopes: bugfixes / security / tests / docs only.
3. Deliver Stage 17 **one workstream at a time** (C1 → S1 → S2 → W1 → L1 → A1 → D1 → H17x) with tests, commit, push, and PR update after each feature.
4. Explicitly out of this pass: Kubernetes/Helm, Prometheus/Grafana/PagerDuty, pg_dump/WAL/S3 PITR, vendor pen test, PgBouncer, paid billing (ADR-002), schema-per-tenant (ADR-001), i18n packs (ADR-006), certified 1000-VU, Open Banking, tax e-file portals, FIFO/LIFO/WA, multi-bin, user↔store membership (ADR-005), WebSocket realtime notifications, Prophet/LLM upgrades, PO Kanban (Stage 2 P2 deferred), reopening Stage 2 I1–I6 / Stage 9–16 frozen feature scopes.

## Consequences

- Agents may implement Stage 17 plan items without reopening Stage 1–16 feature scope.
- Stage 17 exit requires `docs/STAGE_17_EXIT_CRITERIA.md` (created at close) with no CRITICAL/MISSING rows for planned workstreams.
