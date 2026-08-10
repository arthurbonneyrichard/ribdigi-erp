# Stage 16 Fidelity Notes — Multi-Store / Reports / Notifications

**Status:** Closed with Stage 16 D1; exit pending H16x  
**Surface:** Multi-Store → Reports → Notifications  
**Open ADR:** [ADR-037](ADR_037_STAGE16_OPEN.md)  
**Plan:** [STAGE_16_PLAN.md](STAGE_16_PLAN.md)

Stage 16 proves commercial-MVP fidelity on an existing Multi-Store / Reports / Notifications surface — transfer→stock chains, notification emission + channels, report suite alignment to BR-13–15 — **not** multi-bin, WebSocket push, FIFO/LIFO, or ADR-005 user↔store membership.

## Corrections applied

| Area | Before | After |
|------|--------|-------|
| BR-13.1 store ops | All unchecked | Create / inventory / sales / consolidated marked; manager+staff Partial (manager yes; staff membership ADR-005 deferred) |
| BR-13.2 transfers | Only history `[x]` | Create / dual-manager / status / inventory-on-receive marked (M1); history already M2 |
| BR-14 suite | Mostly synced in R1 | Keep universal store/branch filter Partial; Credit/Tax packaging via R2 (no parallel engine) |
| BR-15.1 types | All unchecked | Outline + expense approval + payment_due scan marked (N1 / Stage 1 scan / expense notify) |
| BR-15.2 channels | Already `[x]` (N2) | Guarded in fidelity note; console send-attempt only (no fake carrier delivery) |
| USER_MANUAL §11.2–11.3 | “Reject with reason”; “side-by-side” comparison | Cancel path; by-store / All stores table (not a dual-pane layout) |
| USER_MANUAL §13.1 | Thin category table | Outline buckets + expense / transfer / shift variance |
| PRODUCTION_READINESS multi-store Remaining | Listed N2 open | N2 complete; Remaining = multi-bin + H16x (and ADR-005 / FIFO deferred) |
| API §13.4 | Dual-manager + M2 | + Stage 16 M1 stock chain / `INSUFFICIENT_WAREHOUSE_STOCK` |

## Workstream → evidence → BR → remaining

| WS | Evidence | BR mapping | Remaining |
|----|----------|------------|-----------|
| **M1** | `test_multistore_transfer_chain_m1.py` — create→ship→receive; warehouse qty; `stock_movements`; dual-manager regression; `409 INSUFFICIENT_WAREHOUSE_STOCK` | BR-13.2 inventory-on-receive; BR-13.1 inventory view | Multi-bin |
| **N1** | `test_notification_emission_n1.py` — `low_stock`, `new_order`, `credit_limit`, `purchase_received`, `shift_variance`, `transfer` | BR-15.1 outline types | WebSocket push |
| **R1** | `test_reports_suite_r1.py` — Sales / Inventory / Low Stock / Purchasing / Expenses / Financial / Store Performance + isolation | BR-14.1–14.5 (Partial universal filters) | BS store filter; full financial comparative |
| **R2** | `test_credit_tax_reports_r2.py` — Reports Credit/Tax tabs; export `credit_aging` / `tax*` | Outline Credit/Tax packaging | Tax e-file portals |
| **M2** | `test_transfer_history_m2.py` — filters; `GET /reports/transfers`; export `transfer_history`; Reports → Transfers | BR-13.2 history | — |
| **N2** | `test_notification_channel_delivery_n2.py` — prefs; console email/SMS attempts; pref-off skip | BR-15.2 | No fake carrier `delivered` |
| **D1** | This note + `test_stage16_fidelity_d1.py` | BR-13/14/15 + API + readiness + USER_MANUAL | **H16x** freeze |

## Evidence tests

- `backend/tests/test_multistore_transfer_chain_m1.py`
- `backend/tests/test_notification_emission_n1.py`
- `backend/tests/test_reports_suite_r1.py`
- `backend/tests/test_credit_tax_reports_r2.py`
- `backend/tests/test_transfer_history_m2.py`
- `backend/tests/test_notification_channel_delivery_n2.py`
- `backend/tests/test_inter_store_dual_manager_t1.py` (Stage 4 T1 regression)
- `backend/tests/test_store_sales_context_m1.py` (Stage 4 M1)
- `backend/tests/test_expense_approval_notify.py` (BR-15.1 expense approval)
- `backend/tests/test_stage16_fidelity_d1.py`

## Spec sync targets

- `docs/BUSINESS_REQUIREMENTS_DOCUMENT.md` — BR-13.*, BR-14.5 Partial, BR-15.1/15.2
- `docs/API_DOCUMENTATION.md` — §§13–15 (M1 chain; N2 channel delivery)
- `PRODUCTION_READINESS.md` — multi-store / reports / notifications bullets
- `docs/USER_MANUAL.md` — §§11–13
- `docs/DEVELOPMENT_ROADMAP.md` — Stage 16 D1 note
- `docs/LAUNCH_CHECKLIST.md` — M1–N2 / D1 evidence
- `docs/STAGE_16_PLAN.md` — D1 COMPLETE

## Deferred (not Stage 16)

- Multi-bin / advanced locations
- WebSocket realtime notification push
- FIFO/LIFO/WA costing
- User↔store membership (ADR-005)
- Kubernetes / WAL / S3 PITR; tax e-file portals
- Prophet/LLM upgrades; materialized-view report load suite
- Reopening Stage 4 T1/M1/N1/R1 or Stage 9–15 frozen feature scopes
