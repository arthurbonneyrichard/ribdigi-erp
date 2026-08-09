# Stage 4 Plan — Intelligence, Multi-Store & Scale Hardening

**Status:** Open (ADR-013)  
**Base:** Phase 4 roadmap (`docs/DEVELOPMENT_ROADMAP.md` §5) + BR-13.x–BR-15.x / BR-21.x gaps  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP  

Stage 4 here is **not** a rewrite of multi-store, reports, notifications, or AI. Core engines already exist. This plan closes remaining BR acceptance holes and UX gaps, then freezes Stage 4.

## Delivery rules

1. One workstream at a time (full AC + automated tests before the next).
2. Prefer extending proven patterns (stock transfers, notification prefs, report APIs, AI rule-based services).
3. No demo data / fake success. Alembic for any schema change.
4. After each feature: tests → commit → push → PR update.

## Workstream sequence

| ID | Workstream | Priority | Verdict |
|----|------------|----------|---------|
| **T1** | Inter-store dual-manager approval (BR-13.2) | P0 | COMPLETE |
| **M1** | Global store context + `GET /stores/{id}/sales` (BR-13.1) | P0 | COMPLETE |
| **N1** | `new_order` notification type (BR-15.1) | P0 | COMPLETE |
| **R1** | Sales report depth (customer sales; store/category filters; comparative) | P0 | PENDING |
| **H4** | Stage 4 exit criteria + freeze ADR | Exit | PENDING |

## Explicitly out of this pass

- Prophet / IsolationForest ML upgrades; optional external LLM provider
- WebSocket real-time notification push
- Materialized views / report load performance suite (Phase 5)
- FIFO/LIFO/WA inventory valuation methods
- Multi-bin locations; user↔store membership (ADR-005)
- Paid billing (ADR-002); schema-per-tenant (ADR-001); i18n packs (ADR-006)
- AI document auto-apply / auto-create PO from predictions

## T1 acceptance criteria

- [x] Ship requires source store manager when `manager_id` set; else `403 TRANSFER_SHIP_FORBIDDEN`.
- [x] Receive requires destination store manager when `manager_id` set; else `403 TRANSFER_RECEIVE_FORBIDDEN`.
- [x] `company_admin` / `super_admin` override allowed with audit `transfer_manager_override`.
- [x] Warehouse-only transfers (null store ids) unchanged; unassigned manager keeps prior write access.
- [x] Serialize `from_store_manager_id` / `to_store_manager_id`; Stores UI gates Ship/Receive.
- [x] Automated tests in `backend/tests/test_inter_store_dual_manager_t1.py`.

## M1 acceptance criteria

- [x] `GET /stores/{store_id}/sales` returns tenant-scoped summary (invoice + POS) + recent lines; optional `from_date`/`to_date`/`recent_limit`.
- [x] Foreign store id → 404; `stores` read RBAC.
- [x] Shell global store switcher (All stores + list) persisted in `localStorage` (`selected_store_id`).
- [x] Multi-Store UI Sales panel loads `/stores/{id}/sales` and syncs with global context.
- [x] Automated tests in `backend/tests/test_store_sales_context_m1.py`.

## N1 acceptance criteria

- [x] `new_order` in default notification preferences (dashboard on; email/SMS off by default).
- [x] `new_order` mapped to notifications group `orders`.
- [x] Emit `new_order` on sales-order create and confirm (not `system`).
- [x] Channel preferences honored; tenant isolation on list/filter.
- [x] Automated tests in `backend/tests/test_new_order_notification_n1.py`.

## Sign-off

Stage 4 exit will be recorded in `docs/STAGE_4_EXIT_CRITERIA.md` with a freeze ADR when P0 workstreams are complete.
