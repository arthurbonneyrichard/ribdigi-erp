# Stage 11 Plan — Purchase-to-Pay Chain Fidelity

**Status:** Open  
**Base:** PO → GRN → Inventory → Supplier balance → Accounting → Audit trail  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Exit:** `docs/STAGE_11_EXIT_CRITERIA.md` (at close)

Stage 11 closes end-to-end purchasing chain fidelity after Stage 10 freeze. It is **not** Kubernetes, WAL/PITR, vendor pen test, Open Banking, FIFO/LIFO, or PO Kanban.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (PO line math → GRN valuation; manual PI journals → GRN-linked RC; Stage 9 D1 → fidelity sync).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Chain E2E + GRN valuation fidelity (discount/tax) + AP aging vs received | P0 | PENDING |
| **C2** | GRN-linked PI reverse-charge / AP closeout | P1 | PENDING |
| **A1** | Purchasing audit closeout (payment, PI cancel, GRN→journal assertions) | P1 | PENDING |
| **D1** | Spec / BR / readiness fidelity sync for BR-6.x chain | P2 | PENDING |
| **H11x** | Stage 11 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm; full Prometheus/Grafana/PagerDuty
- pg_dump / WAL / S3 offsite PITR; vendor pen test; PgBouncer
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Certified 1000-VU; Prophet/LLM; multi-bin; PO Kanban
- Open Banking; tax e-file portals; FIFO/LIFO/WA costing
- User↔store membership (ADR-005)

## C1 acceptance criteria

- [ ] GRN `accepted_value` uses PO line math (discount + tax), scaled for partial qty.
- [ ] PI created from GRN carries proportional line discount (matches GRN AP).
- [ ] Uninvoiced AP aging uses received value (not full unordered PO total); zero received → not aged as AP.
- [ ] Automated E2E: PO → send → GRN → stock ↑ → supplier balance ↑ → GRN journal → PI from GRN (no double AP) → payment → balance ↓.

## C2 acceptance criteria

- [ ] GRN-linked reverse-charge PI posts self-assess tax only (no second Inv/AP).
- [ ] Automated tests for the RC closeout path.

## A1 acceptance criteria

- [ ] Domain audit for supplier payment and PI cancel (at minimum).
- [ ] Tests assert `grn_posted` + inventory/journal linkage on the chain.

## D1 acceptance criteria

- [ ] BR-6.x / API / readiness / launch checklist aligned with C1–A1 evidence.

## H11x acceptance criteria

- [ ] `docs/STAGE_11_EXIT_CRITERIA.md` records C1/C2/A1/D1/H11x COMPLETE with evidence.
- [ ] Scope freeze ADR accepted; automated guard test present.

## Sign-off

Stage 11 remains open until H11x exit criteria and freeze ADR are recorded.
