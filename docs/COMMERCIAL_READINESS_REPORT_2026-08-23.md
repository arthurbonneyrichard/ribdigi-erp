# RIBDIGI ERP — Commercial Readiness Report (2026-08-23)

**Mode:** Audit synthesis + first code hardening pass. **Packaging ≠ product Completes.**

**Authoritative audit spines:** `PRODUCTION_READINESS.md`, `docs/CHANGE_IMPACT_MVP_UPDATE_2026-08-14.md`, `docs/LAUNCH_CHECKLIST.md` + `ops/launch/checklist-map.json`.

---

## Verdict summary (Section 60)

| Area | Status |
|------|--------|
| Architecture (shared-schema tenancy) | **PASS** (runtime) — doc drift **NEEDS HARDENING** |
| Tenant isolation | **PASS** (MVP automated tests) |
| Multi-company | **PARTIAL** — entitlement gates COMPLETE; single-company UX hides switcher when `max_companies === 1` |
| Company entitlement | **COMPLETE** (MVP) — plan-synced `max_companies` + platform override (2026-08-23) |
| Store entitlement | **COMPLETE** (MVP) |
| User entitlement | **COMPLETE** (MVP) — plan-synced `max_users` + platform override; create/reactivate enforced (2026-08-23) |
| User ↔ Store assignment | **MISSING** (ADR-005 POST-MVP) |
| RBAC / store scope | **PARTIAL** — store_manager scoped via `manager_id`→`Warehouse.store_id` across POS/sales/expenses/stores/transfers/inventory ops/purchasing PR/PO/GRN/returns + purchase invoices via linked PO/GRN WH (manual unlinked PIs fail-closed); ADR-005 still open |
| Inventory / Purchasing / Sales / Accounting / Tax / Credit | **PASS** (MVP gates in `PRODUCTION_READINESS.md`) |
| POS (online) | **PASS** (MVP) |
| Offline foundation | **PARTIAL** — queue/catalog/sync MVP; 7-day auth envelope implemented (not VERIFIED) |
| 7-Day offline | **PARTIAL** (envelope + client gate shipped; physical endurance **NOT RUN**) |
| Offline recovery / lockdown / owner dashboard | **PARTIAL** — recovery export UI + owner alerts API/UI; lockdown / Offline Complete still MISSING |
| Paid billing | **DEFERRED** (ADR-002) |
| Backup (logical) | **PASS** (MVP tests) |
| Restore / PITR / load / pen test (live) | **NOT RUN** (operator/external) |
| Production deployment | **NOT READY** (cutover not executed) |
| Documentation | **DRIFT EXISTS** (being corrected) |
| **Go-live** | **NOT READY** |

---

## Launch blockers (code + operator)

1. **Go-live not executed** — `go_live_claimed: false`; LAUNCH §1–3 unchecked; §7 unsigned.
2. **Paid billing missing** — ADR-002; blocks revenue launch.
3. **Production cutover not performed** — `production_cutover_claimed: false`.
4. **Live PITR / restore drill** — packaged runbooks only; `operator_pitr_drill_executed: false`. See `docs/PITR_RESTORE_DRILL_RUNBOOK_2026-08-23.md` + `docs/DR_WAL_PITR_RUNBOOK.md`.
5. **Architecture doc drift** — **partially fixed** 2026-08-23 (`DATABASE_DOCUMENTATION.md`, `ARCHITECTURE_DOCUMENTS.md`); audit remaining top-level docs.
6. **`max_users` enforcement** — **implemented** 2026-08-23 (plan sync + platform override + create/reactivate/import gate). Downgrades preserve users; `over_entitlement` on tenant dashboard.
7. **Default store on company create** — **implemented** 2026-08-23 when store capacity allocated.
8. **ADR-005 user↔store membership** — POST-MVP if product requires cashier store lists.
9. **Store RBAC** — **PARTIAL** (2026-08-23): `store_manager` constrained on POS/sales/expenses/stores/transfers, warehouse inventory ops, purchasing PR/PO/GRN/returns, and **purchase invoices** (scope inferred from linked GRN/PO `warehouse_id`; manual unlinked invoices fail-closed; no direct PI `warehouse_id` column yet). ADR-005 membership still open.
10. **7-day offline POS** — **PARTIAL** (2026-08-23): envelope + client gate. Physical matrix: `docs/OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md` (**NOT RUN** / not VERIFIED).
11. **Offline owner dashboard + alerts + recovery** — **PARTIAL**: recovery export + alerts API/UI; email/push + lockdown + Offline Complete MISSING.
12. **Scale / pen test on prod infra** — operator/external.
13. **Commercial tip migrations** — apply `0106`→`0107`→`0108` before prod bind/entitlement paths (`docs/COMMERCIAL_DEPLOY_MIGRATIONS_2026-08-23.md`, `ops/launch/commercial-tip-migrations.json`).

---

## Code changes this pass (not documentation packs)

- **Default Main Store on company create** when `create_main_store` (default when company has `store_limit ≥ 1`); blocks explicit request without allocation (`STORE_LIMIT_REQUIRED`). Tests: `test_company_create_creates_main_store_when_capacity_allocated`, `test_company_create_blocks_main_store_without_allocation`.
- **UI:** Companies page checkbox “Create Main Store automatically”.
- **Docs:** Mark schema-per-tenant as SUPERSEDED; point to `docs/ADR_001_TENANCY.md`.
- **Offline payment safety (§18):** POS blocks cashier card/wallet offline; supervisor acknowledgment + pending-verification metadata for provider methods; offline credit requires cached customer data + credit permission. Server `/sync/push` rejects unsafe offline payments (`OFFLINE_PAYMENT_BLOCKED`, `OFFLINE_CREDIT_BLOCKED`). Tests: `test_offline_payment_safety.py`.
- **Unsafe local reset guard (§23):** `offlineQueue.ts` throws `OfflineQueuePendingError` when clearing/resetting with pending ops (recovery export always allowed).
- **Offline recovery export UI (§23 follow-through):** Company `#offline-sync` + POS “Export offline recovery pack” downloads secret-free JSON (`downloadOfflineRecoveryPack`) of pending/failed ops + envelope metadata; **never clears the queue**. Owner alerts, native shells, and Offline Complete remain MISSING.
- **Owner offline summary:** Company `#offline-sync` tenant summary card (device counts, server pending pushes/pulls, conflicts via `/sync/status`).
- **7-day offline auth envelope (§13–14):** `offline_auth_envelope.py` + Alembic `20260823_0106`; `POST /offline/devices/{id}/bind`; client IndexedDB (`offlineAuthEnvelope.ts`); POS blocks new offline sales when `offline_valid_until` expired (queue preserved). Tests: `test_offline_auth_envelope.py`. **Does not claim Offline Complete or 7-day VERIFIED.**
- **Company entitlement:** `PLAN_CATALOG.soft_limits.companies` syncs `Tenant.max_companies` on plan change; platform `PATCH /platform/tenants/{id}/company-entitlement` for override/unlimited; downgrades preserve companies and block new creates. Tests: `test_company_entitlements.py`.
- **Platform UI for company-entitlement override:** House tenant detail (`/platform/tenants/[id]`) mirrors store-entitlement controls (base / override / unlimited −1 / clear) via `PATCH /platform/tenants/{id}/company-entitlement`. Caps only — not paid billing Completes.
- **Platform UI for user-entitlement override:** House tenant detail mirrors company/store controls (base / override / unlimited −1 / clear) via `PATCH /platform/tenants/{id}/user-entitlement`; shows `user_count` from platform tenant payload. Caps only — not paid billing Completes.
- **User entitlement:** `PLAN_CATALOG.soft_limits.users` syncs `Tenant.max_users` on plan change (unless override); platform `PATCH /platform/tenants/{id}/user-entitlement`; create/reactivation/import blocked at limit (`USER_LIMIT_REACHED`); downgrades never delete users; tenant dashboard exposes `user_entitlement` / `over_entitlement`. Tests: `test_user_entitlements.py`. Alembic `20260823_0108` (`max_users_override`). Deploy: apply `0106` → `0107` → `0108` in order (`0107` revises `0106`).
- **Single-company UX:** `/me` and `/workspace` expose `company_entitlement`; Shell hides workspace switcher for non–tenant-admin users on single-company plans with one company; Companies page hides create-at-limit and redundant switch controls.
- **Offline owner alerts:** `offline_alerts.py` + `GET /offline/alerts` (envelope expired/expiring, never bound, sync backlog/failed, open conflicts); Company `#offline-sync` alert list. In-app only — not email/push Complete.
- **Offline receipt numbering:** client IndexedDB seq per device (`offlineReceiptNumber.ts` → `OFF-{device}-{seq}`); POS shows receipt on queue; `/sync/push` preserves as sale `reference` with duplicate guard (`OFFLINE_RECEIPT_DUPLICATE`). Tests: `test_offline_receipt_numbering.py`.
- **Operator runbooks (2026-08-23):** commercial Alembic deploy note; offline physical test matrix; PITR drill wrapper — all unchecked / not executed; go-live still NOT READY.
- **Store RBAC ops hardening:** store + warehouse helpers through POS/sales/expenses/stores/transfers, warehouses/inventory ops, purchasing PR/PO/GRN/returns, and purchase invoices via PO/GRN warehouse join (`apply_purchase_invoice_warehouse_scope`; unlinked manual PIs denied for managers). Tests: `test_store_scope_ops_hardening.py`. Does not claim store-scoped RBAC Complete or ADR-005.
- **Architecture doc drift:** `ARCHITECTURE_DOCUMENTS.md` §9.1 and `DATABASE_DOCUMENTATION.md` §§3.1–3.4 schema-per-tenant SQL samples marked historical / SUPERSEDED (live = shared-schema `tenant_id`).

---

## ACTION REQUIRED FROM OWNER

1. LAUNCH §1–3 verification (secrets, CORS, Redis, SMTP, no demo creds).
2. Staging → production cutover on target VPS/domain/HTTPS — apply Alembic `0106`→`0107`→`0108` first (`docs/COMMERCIAL_DEPLOY_MIGRATIONS_2026-08-23.md`).
3. Execute PITR + restore drill in staging/prod; retain evidence (`docs/PITR_RESTORE_DRILL_RUNBOOK_2026-08-23.md`).
4. Physical POS offline tests (Windows/Android/iPad/macOS) per `docs/OFFLINE_PHYSICAL_TEST_RUNBOOK_2026-08-23.md`.
5. Production load test (~1000 VU) on sized infra.
6. Vendor penetration test engagement.
7. Decide billing provider integration timeline (ADR-002).
8. Sign LAUNCH §7 after evidence review.

---

## Offline POS (sections 13–38) — audit complete

**Honest positioning:** partial offline queue MVP; **Offline Complete explicitly MISSING** (`docs/OFFLINE_COMPLETE_ATTESTATION.md`).

| Shipped | Not shipped |
|---------|-------------|
| IndexedDB queue + catalog, sync APIs, device registry/revoke, idempotent `client_request_id`, offline payment safety (cash default; provider ack), queue reset guard, tenant offline summary on Company page, **7-day auth envelope (bind + IndexedDB + POS gate + sync validation)**, **local recovery export UI** (Company + POS; queue preserved; no tokens), **owner offline alerts API + Company UI** (in-app; not email/push), **offline receipt numbering** (`OFF-{device}-{seq}`; sync preserves reference) | Offline Complete attestation, 7-day physical VERIFIED, email/push alerts, native shells, hardware bridges |

**Physical tests** (7-day endurance, multi-device reconnect, peripherals) require owner/device action — not runnable in CI alone.

---

*Offline POS audit: sections 13–38 complete (2026-08-23).*
