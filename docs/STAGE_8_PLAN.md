# Stage 8 Plan — Credit Fidelity & AP Cash Closeout

**Status:** Open (ADR-021)  
**Base:** BR-11.2 / remaining credit + purchasing UI fidelity after Stage 7 freeze  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  

Stage 8 closes commercial-MVP AP/credit holes that are documented but unfinished. It is **not** Kubernetes, WAL/PITR, vendor pen test, or paid billing.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (outstanding/aging → payment schedule; return API → multi-line UI).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **S1** | Supplier payment schedule (API + Credit UI) | P0 | COMPLETE |
| **S2** | Outstanding bills UI (AP + AR) | P1 | PENDING |
| **A1** | Account ledger transactions (`GET …/accounts/{id}/transactions`) | P1 | PENDING |
| **P1** | Purchase return multi-line UI | P1 | PENDING |
| **H8x** | Stage 8 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm production chart review
- Full Prometheus/Grafana/PagerDuty stack
- pg_dump / WAL / S3 offsite PITR
- Vendor penetration test / ZAP-in-CI full Top 10
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- Certified 1000-VU staging run; Prophet/LLM; multi-bin; PgBouncer
- PO Kanban (Stage 2 P2 optional polish)

## S1 acceptance criteria

- [x] `GET /suppliers/{id}/payment-schedule` returns overdue/upcoming items sorted by due date.
- [x] Includes amounts, `days_until_due`, schedule buckets, and early-discount quotes for open purchase invoices.
- [x] Tenant-scoped + `credit:read` RBAC; 404 for missing supplier.
- [x] Credit UI (Payables) shows Payment schedule table.
- [x] Automated tests in `backend/tests/test_supplier_payment_schedule_s1.py`.

## Sign-off

Stage 8 exit will be recorded in `docs/STAGE_8_EXIT_CRITERIA.md` with a freeze ADR when planned workstreams are complete.
