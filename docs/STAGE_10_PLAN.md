# Stage 10 Plan — Tax Fidelity & Document Workflow Closeout

**Status:** Open  
**Base:** BR-12.1 / tax + document workflow fidelity after Stage 9 freeze  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Exit:** `docs/STAGE_10_EXIT_CRITERIA.md` (at close)

Stage 10 closes commercial-MVP tax depth and human-confirmed document apply holes. It is **not** Kubernetes, WAL/PITR, vendor pen test, tax portal e-file, or FIFO/LIFO.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (product `tax_rate_id` → category rate; GH/NG filing packs → another jurisdiction; OCR suggest → explicit apply).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **T1** | Category-level tax rules (product → category → default) | P0 | COMPLETE |
| **T2** | Additional tax filing template beyond GH/NG | P1 | PENDING |
| **A1** | Human-confirmed OCR/document apply-to-draft | P1 | PENDING |
| **B1** | Include uploaded media in logical backup/restore | P2 | PENDING |
| **H10x** | Stage 10 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm; full Prometheus/Grafana/PagerDuty
- pg_dump / WAL / S3 offsite PITR; vendor pen test; PgBouncer
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Certified 1000-VU; Prophet/LLM; multi-bin; PO Kanban
- Open Banking; tax e-file portals; FIFO/LIFO/WA costing
- User↔store membership (ADR-005)

## T1 acceptance criteria

- [x] `product_categories.tax_rate_id` via Alembic; serialize on category APIs.
- [x] `resolve_product_tax`: product rate → category (walk parents) → tenant default; product exempt still wins.
- [x] Catalog create/PATCH accepts `tax_rate_id` (tenant-scoped active rate); Inventory UI can set it.
- [x] Automated tests in `backend/tests/test_category_tax_t1.py`.

## T2 acceptance criteria

- [ ] At least one filing template pack beyond GH/NG (export + Reports surface).
- [ ] Docs state no portal e-file.
- [ ] Automated tests for the new packing/export type.

## A1 acceptance criteria

- [ ] Explicit apply endpoint(s) for OCR suggestions → draft fields (expenses and/or purchase invoices).
- [ ] No silent auto-write; human confirmation required.
- [ ] Automated tests for apply + RBAC/tenant.

## B1 acceptance criteria

- [ ] Logical `.ribbak` backup/restore includes uploaded media objects (or documented keys + restore).
- [ ] Automated tests cover media round-trip or manifest inclusion.

## H10x acceptance criteria

- [ ] `docs/STAGE_10_EXIT_CRITERIA.md` records T1/T2/A1/B1/H10x COMPLETE with evidence.
- [ ] Scope freeze ADR accepted; automated guard test present.

## Sign-off

Stage 10 remains open until H10x exit criteria and freeze ADR are recorded.
