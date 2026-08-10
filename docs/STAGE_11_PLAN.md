# Stage 11 Plan — Purchase-to-Pay Chain Fidelity

**Status:** Closed — exit met; freeze [ADR-028](ADR_028_STAGE11_FREEZE.md)  
**Base:** PO → GRN → Inventory → Supplier balance → Accounting → Audit trail  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Exit:** [STAGE_11_EXIT_CRITERIA.md](STAGE_11_EXIT_CRITERIA.md)  
**Fidelity:** [STAGE_11_FIDELITY.md](STAGE_11_FIDELITY.md)

Stage 11 closes end-to-end purchasing chain fidelity after Stage 10 freeze. It is **not** Kubernetes, WAL/PITR, vendor pen test, Open Banking, FIFO/LIFO, or PO Kanban.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (PO line math → GRN valuation; manual PI journals → GRN-linked RC; Stage 9 D1 → fidelity sync).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **C1** | Chain E2E + GRN valuation fidelity (discount/tax) + AP aging vs received | P0 | COMPLETE |
| **C2** | GRN-linked PI reverse-charge / AP closeout | P1 | COMPLETE |
| **A1** | Purchasing audit closeout (payment, PI cancel, GRN→journal assertions) | P1 | COMPLETE |
| **D1** | Spec / BR / readiness fidelity sync for BR-6.x chain | P2 | COMPLETE |
| **H11x** | Stage 11 exit criteria + freeze ADR | Exit | COMPLETE |

## Explicitly out of this pass

- Kubernetes / Helm; full Prometheus/Grafana/PagerDuty
- pg_dump / WAL / S3 offsite PITR; vendor pen test; PgBouncer
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Certified 1000-VU; Prophet/LLM; multi-bin; PO Kanban
- Open Banking; tax e-file portals; FIFO/LIFO/WA costing
- User↔store membership (ADR-005)

## C1 acceptance criteria

- [x] GRN `accepted_value` uses PO line math (discount + tax), scaled for partial qty.
- [x] PI created from GRN carries proportional line discount; `_prepare_invoice_lines` tax-on-net-after-discount.
- [x] Uninvoiced AP aging uses received value (not full PO total); zero received → not aged as AP.
- [x] Automated E2E in `backend/tests/test_purchasing_chain_c1.py`.

## C2 acceptance criteria

- [x] GRN-linked reverse-charge PI posts self-assess tax only (`skip_inventory_ap`; Dr 1300 / Cr 2100).
- [x] Cancel reverses RC-only; GRN AP/balance untouched. Tests: `backend/tests/test_grn_linked_rc_c2.py`.

## A1 acceptance criteria

- [x] Domain audit `supplier_payment_recorded` + `purchase_invoice_cancelled`; richer `grn_posted` balance details.
- [x] Tests assert `grn_posted` + `journal_posted` (source_type=grn) + payment/cancel hash chain (`test_purchasing_audit_a1.py`).

## D1 acceptance criteria

- [x] BR-6.x / API / readiness / launch checklist aligned — `docs/STAGE_11_FIDELITY.md`.

## H11x acceptance criteria

- [x] `docs/STAGE_11_EXIT_CRITERIA.md` records C1/C2/A1/D1/H11x COMPLETE with evidence.
- [x] Scope freeze ADR-028 accepted; automated guard test `backend/tests/test_stage11_exit_h11x.py`.

## Sign-off

Stage 11 exit is met. Feature scope is frozen under ADR-028 (bugfixes / security / tests / docs only until CONTINUE opens the next track).
