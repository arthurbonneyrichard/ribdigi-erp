# Stage 16 Plan — Multi-Store / Reports / Notifications Fidelity

**Status:** Open  
**Base:** Multi-Store → Reports → Notifications  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  
**Open ADR:** [ADR-037](ADR_037_STAGE16_OPEN.md)

Stage 16 closes commercial-MVP fidelity on the Multi-Store / Reports / Notifications surface after Stage 15 freeze. Engines already exist (Stages 1–4 / 9 / 14). This track proves transfer→stock chains, notification emission coverage, report suite alignment to BR-13–15 and the product outline, and docs sync — **not** multi-bin, WebSocket push, FIFO/LIFO, or greenfield Multi-Store.

## Product outline (owner)

```
Multi-Store
 ├── Warehouses
 ├── Stock per location
 ├── Transfers
 ├── Transfer receiving
 └── Central management

Reports
 ├── Sales
 ├── Inventory
 ├── Low Stock
 ├── Purchasing
 ├── Expenses
 ├── Credit
 ├── Tax
 ├── Financial
 └── Store Performance

Notifications
 ├── Low Stock
 ├── Important Sales Events
 ├── Credit Alerts
 └── Operational Alerts
```

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (Stage 4 T1 dual-manager / M1 store context / N1 `new_order` / R1 sales depth; Stage 9 purchase+inventory reports; Stage 14 financial store dims).
3. No demo data / fake success. Alembic only when schema is required.
4. After each feature: tests → commit → push → PR update.
5. Do not reopen Stage 1–15 feature scopes; do not re-implement Stage 4 dual-manager UX or rewrite Credit/Tax engines.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **M1** | Transfer → stock chain proof (ship/receive → warehouse qty + movements) | P0 | COMPLETE |
| **N1** | Notification emission proof matrix (low stock, sales, credit, operational) | P0 | COMPLETE |
| **R1** | Reports suite fidelity (Sales / Inventory / Low Stock / Purchasing / Expenses / Financial / Store Performance) | P0 | COMPLETE |
| **R2** | Credit + Tax report packaging fidelity (Reports outline ↔ existing APIs/UI) | P1 | COMPLETE |
| **M2** | Transfer history / consolidated multi-store ops reporting | P1 | COMPLETE |
| **N2** | Channel delivery hardening (email/SMS prefs for key categories) | P1 | PENDING |
| **D1** | Spec / BR-13–15 / readiness fidelity sync | P2 | PENDING |
| **H16x** | Stage 16 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Kubernetes / Helm; Prometheus/Grafana/PagerDuty; PgBouncer
- pg_dump / WAL / S3 offsite PITR; vendor pen test; certified 1000-VU
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n (ADR-006)
- Native Open Banking; tax authority e-file portals
- FIFO/LIFO/WA; multi-bin / advanced locations
- User↔store membership (ADR-005); WebSocket realtime notification push
- Prophet/LLM upgrades; materialized-view report load suite
- Reopening Stage 4 T1/M1/N1/R1 or Stage 9–15 frozen feature scopes

## M1 acceptance criteria

- [x] Live inter-store transfer create → ship → receive updates source/destination warehouse quantities and writes `stock_movements` (reference transferable to inventory movements report).
- [x] Dual-manager ship/receive gates remain enforced (regression guard only; do not rewrite Stage 4 T1).
- [x] Insufficient source warehouse stock on ship → `409 INSUFFICIENT_WAREHOUSE_STOCK`; transfer stays `requested`; no movements.
- [x] Automated proof: `backend/tests/test_multistore_transfer_chain_m1.py`.

## N1 acceptance criteria

- [x] Prove emissions for outline buckets: Low Stock (`low_stock` scan), Important Sales Events (`new_order`), Credit Alerts (`credit_limit` on invoice post ≥80% utilization), Operational Alerts (`purchase_received`, `shift_variance`, `transfer`).
- [x] Prefer HTTP/service proofs over planted notification rows; prefs categories honored (`shift_variance` dashboard off suppresses targeted note).
- [x] Automated proof: `backend/tests/test_notification_emission_n1.py`.

## R1 acceptance criteria

- [x] Documented + automated coverage that Reports outline items Sales, Inventory, Low Stock, Purchasing, Expenses, Financial, Store Performance resolve to live APIs (and UI tabs where present) with tenant isolation.
- [x] Align BR-14.1 / 14.4 / 14.5 checkboxes only when evidence exists; store/branch-universal filters remain Partial where noted.
- [x] Automated proof: `backend/tests/test_reports_suite_r1.py`.

## R2 acceptance criteria

- [x] Credit and Tax appear in the Reports product story without a parallel engine: Reports UI tabs + cross-links to `/credit` and `/tax`; export `credit_aging` / existing `tax` + `tax_filing`.
- [x] Automated proof: `backend/tests/test_credit_tax_reports_r2.py`.

## M2 acceptance criteria

- [x] Transfer history / consolidated ops view or report/export from existing inter-store (and optionally warehouse) transfers — not multi-bin.
- [x] Automated proof for list/filter/export path chosen: `backend/tests/test_transfer_history_m2.py` (`GET /stores/transfers` filters, `GET /reports/transfers`, export `transfer_history`, Reports → Transfers tab).

## N2 acceptance criteria

- [ ] Email and/or SMS delivery path proven for at least two outline categories with user channel preferences respected (console/Twilio fallbacks OK in test).
- [ ] Automated proof: channel prefs + send attempt recorded (no fake “delivered to carrier” success).

## D1 acceptance criteria

- [ ] BR-13/14/15, API, readiness, user manual aligned — `docs/STAGE_16_FIDELITY.md`.
- [ ] Guard test: `backend/tests/test_stage16_fidelity_d1.py`.

## H16x acceptance criteria

See workstream table; filled when exit workstream starts.

## Sign-off

M1–M2 complete. Pending N2 → D1 → H16x.
