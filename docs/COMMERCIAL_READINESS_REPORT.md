# RIBDIGI ERP COMMERCIAL READINESS REPORT

**Date:** 2026-09-17 (historical scorecard). **2026-10-13 addendum** is the latest retail result. Earlier addenda stay below.

## 2026-10-13 addendum (retail count-and-close)

**Ready for market. Not certified.** Retail can be sold as a controlled release from this tree. Certification still needs the checks listed below. Offline scope stays offline POS. `offline_complete_claimed` stays false.

### What changed

- Shift report on POS now records counted cash and closes that open shift. A difference requires a short note. Pending offline sales for that shift block the close. Sign-out still closes at the expected drawer amount.
- Gift-card and loyalty redemption no longer debit cash account 1000. A gift card posts to liability 2150. Loyalty points post to liability 2160. Issuing a card debits expense 6100 because that screen does not collect money. A named customer earns 1% of the sale, and that award debits expense 6110 and credits 2160. A walk-in earns no points.

### Verified in this pass

- `tests/test_pos_cash_movements.py`: **3 passed** in 8.20s (cash in/out variance, cashier cannot close another shift, counted-cash control present and sign-out still uses expected cash). Frontend typecheck was run separately.
- The 120-case retail checklist is not in this repository. It was not run.
- Signed-in browser walkthrough was not run. No password was entered.
- Isolated Postgres restore is recorded in the later checks below.

### 2026-10-13 later checks

- Unreachable API copy now says the device is offline or the server did not respond, and it tells the user to reconnect. Sign-in still cannot succeed while disconnected. Pending Point of Sale sales stay on the device until sync succeeds.
- Arithmetic fixture on a disposable test database: opening stock 20, unit cost 60, tax-exclusive price 100, tax 10%, quantity 2. Result: total 220, subtotal 200, tax 20, cash debit 220, revenue credit 200, tax credit 20, COGS debit 120, inventory credit 120, stock left 18, one journal. Repeating the same `client_request_id` returned the original sale. `tests/test_retail_pos_arithmetic_fixture.py`: **1 passed** in 6.00s. `tests/test_pos_sale_client_request_id_idempotent.py` passed in the same session. The 10% rate is a test fixture, not tax guidance.
- Last active company admin: soft deactivate, role change, and delete are refused while that person is the only active company admin. After a second company admin exists, the original admin can be reassigned. `tests/test_users_roles.py` plus `tests/test_users_delete_account_r1.py`: **6 passed** in 20.67s.
- Isolation, store caps, offline POS sync, and subscription billing: **57 passed** in 178.39s (`test_tenant_isolation_matrix.py`, `test_subscription_store_limits_r1.py`, `test_offline_pos_isolation.py`, `test_saas_billing_r1.py`).
- Local Postgres restore rehearsal: `pg_dump` of `ribdigi_erp` restored into a new database `ribdigi_restore_drill` in 16.57s. Counts matched the source (tenants 5, users 7, products 3, transactions 35, journal entries 36, stock movements 42). Every company had zero unbalanced journals. The drill database was dropped. The app database was not overwritten. This was a local copy, not a production backup file.
- Sales documents, cashier POS limits, and stores: **12 passed** in 8.69s (`test_sales_docs.py`, `test_sales.py`, `test_cashier_pos_only.py`, `test_stores.py`).
- Gift cards and loyalty: a named sale earns 1% and posts liability 2160, not cash. POS collects **Gift card code** only when the tender is a gift card and sends that code as the tender reference. There is no general payment-reference box. Gift-card code, loyalty earn, and cash-routing checks: **5 passed** in 14.15s.

### Not certified until

- Signed-in single-store and multi-store retail walkthrough beyond this one POS sale.
- Live site was not tested.
- One local offline POS sale was walked on company `offline-drill-oct13`: prepare online, disconnect, sell cash, reload, reconnect, sync. Sale, stock, balanced journal, tender, and open shift totals matched. Offline mode is not certified.

## 2026-10-05 addendum (local production tree)

**Not ready for market.** The full backend suite is green. The isolated Postgres restore and the signed-in browser walkthrough are still open. `offline_complete_claimed` stays false. Offline scope is offline POS only.

### Verified

- Targeted behavioral slice: 38 passed, exit 0, ended 2026-10-04T23:59:14Z.
- Isolated sqlite restore: 2 passed, 5.44s. Create, dry-run, apply, verify. Not a Postgres restore.
- Frontend build after the UI contract edits: Next.js 14.2.35, 44/44 pages, exit 0, ended 2026-10-05T02:25:52Z. Brand green `#4AB012` is unchanged. The `themeColor` metadata warning is cleared by keeping the color on `viewport` only.
- Full backend pytest: **2855 passed, 1 skipped**, 36257 warnings, 4345.20s, exit 0, ended 2026-10-05T10:09:14Z. Command: `PYTHONPATH=.` and `python -m pytest -q --tb=line` from `backend` on Python 3.12.10. Prior counts kept for the trail: 112 failed / 2743 passed (2026-10-04T23:25:55Z), then 1 failed / 2854 passed (2026-10-05T04:53:20Z).
- Authenticated load smoke, same 2000ms target. Focused command: `python -m pytest tests/test_loadtest_baseline_l1.py::test_baseline_authenticated_scenarios_asgi -q --tb=line` (concurrency 3, 5 iterations, login + products + dashboard). Idle: login p50 469.62ms / p95 604.73ms, products p95 592.36ms, dashboard p95 462.47ms, run 2454ms, 1 passed in 5.43s. With eight busy CPU processes: login p95 593.89ms, products p95 524.31ms, dashboard p95 473.72ms, 1 passed in 5.55s. The full suite above includes this test. Measured cause of the 2526.3ms miss: bcrypt cost 12 (`verify_password` about 240ms) ran on the asyncio event loop, so three concurrent verifies finished at 256ms, 523ms, and 734ms. The same three calls on worker threads finished together near 230ms. Login, disable-2FA, and change-password now use `asyncio.to_thread`. Hash rounds, rate limits, audit, and the 2000ms target were not changed.

### Blocked

- Isolated Postgres restore. Listener 127.0.0.1:5432 is the live app database `ribdigi_erp` only. No disposable database and no `.ribbak`. See the operator steps in `docs/DR_LOGICAL_BACKUP_RUNBOOK.md`.
- Browser sign-in and on-screen receipt preview. Login form is up at `http://127.0.0.1:3000/` on the Docker frontend image. Password was not entered. API walkthroughs do not close this gate.
- `metadataBase` warning remains because no public site origin is configured.

### Owner tasks (still incomplete)

Production HTTPS, secrets, workers, load certification, and physical POS checks.
  
**Code HEAD (this workstream):** see branch `production`  
**Principle:** No false completion. Automation cannot execute physical POS / VPS / pen tests.

## 2026-10-04 QA addendum (local production tree)

Go-live remains **NOT READY**. The full backend suite on this tree failed. Isolated sqlite restore and the signed-in API walkthrough are recorded in `docs/GO_LIVE_CHECKLIST.md`. A production database was not restored. Offline POS is the only offline surface; the rest of the ERP is online-only. `offline_complete_claimed` stays false.

| Check | Result |
|-------|--------|
| Isolated sqlite backup/restore | PASS — 2 passed in 5.44s. Create, dry-run validate, apply, verify. Other tenant untouched. Queued offline sales remain and can be dismissed. Store and warehouse ownership restored. Failed proof returns 409 and leaves no partial product or store name. |
| Frontend production build | PASS — `npm run build` in `frontend`, Next.js 14.2.35, 44/44 pages, exit 0 (2026-10-04T21:59:44Z). |
| Signed-in retail and pharmacy, single and multi | PASS (API) — POS shift, Mobile Money sale, receipt, daily sales report, single-store transfer 403, multi-store transfer 200, pharmacy dashboard desk, expired and quarantined lots 409. Browser password entry was not driven. |
| Full backend pytest | FAIL — 112 failed, 2743 passed, 1 skipped, 35745 warnings, 3631.66s, exit 1. Sampled failures match clean HEAD. Not a missing-service result. |

---

## Scorecard

| Area | Verdict |
|------|---------|
| Architecture | **PASS** (shared schema + `tenant_id`; Tenant == Company profile for MVP) |
| Tenant Isolation | **PASS** |
| Multi-Company | **PARTIAL** — 1 Company profile per Tenant by design; child Companies **POST-MVP** |
| Company Entitlement | **PARTIAL** — `max_companies` informational (=1); store entitlements authoritative |
| Store Entitlement | **COMPLETE** |
| User ↔ Store Assignment | **COMPLETE** (membership model + POS enforcement; empty = grandfather all) |
| RBAC | **PASS** |
| Inventory | **PASS** |
| Purchasing | **PASS** |
| Sales | **PASS** |
| POS (online) | **PASS** |
| Accounting | **PASS** |
| Tax | **PASS** |
| Credit | **PASS** |
| Offline Foundation | **PARTIAL** (IndexedDB queue + 7-day envelope + idempotent `client_request_id`; endurance/device certification NOT RUN) |
| 7-Day Offline | **NOT RUN** (auth window implemented; physical 7-day endurance not executed) |
| Offline Recovery | **PARTIAL** (JSON export/import of pending queue + envelope metadata; no secrets; physical recover drill NOT RUN) |
| POS Device Monitoring | **PARTIAL** (`pos_devices` heartbeat upsert + list API; no alert dashboard / MDM) |
| POS Device Lockdown | **PARTIAL** (app cash-offline rules + reset guard; OS guide in `docs/POS_DEVICE_LOCKDOWN_GUIDE.md`; physical kiosk verification NOT RUN) |
| Windows / Android / iPadOS / macOS POS | **NOT VERIFIED** |
| Backup | **PASS** (logical) |
| Restore | **PASS** (logical CI drill) / prod restore **NOT RUN** |
| PITR | **NOT RUN** (runbook only) |
| Load Test | **NOT RUN** (baseline docs only) |
| Internal Security | **PASS** |
| External Penetration Test | **NOT EXECUTED** |
| Production Deployment | **NOT READY** |
| Paid Billing | **DEFERRED** (entitlements live; gateway not integrated) |
| Documentation | **CURRENT** with drift marks on obsolete tenancy claims |
| **Go-Live** | **NOT READY** |

---

## What this phase completed (code)

1. **Default Main Store** on tenant seed (entitlement-aware via `create_store`)  
2. **UserStoreMembership** model + migration `20260917_0105`  
3. **Store RBAC** — `GET/PUT /users/{id}/stores`; POS store list + open session enforce membership  
4. **Docs honesty** — SUPERSEDED markers for database-per-tenant claims  
5. **Auth gate / store parity** (prior commits on this branch)  
6. **Offline POS foundation** — IndexedDB queue + 7-day auth envelope (`frontend/lib/posOffline.ts`), SW shell cache (`public/sw.js`), POS cash-only offline checkout + auto-flush, `client_request_id` idempotency (migration `20260917_0106`)  
7. **Offline recovery package** — export/import pending queue JSON (no tokens) from POS UI  
8. **POS device heartbeat** — `pos_devices` table (migration `20260917_0107`), `POST /pos/devices/heartbeat`, `GET /pos/devices`  
9. **OS lockdown guide** — `docs/POS_DEVICE_LOCKDOWN_GUIDE.md` (guidance only; hardware NOT VERIFIED)  
10. **This checklist + report**

---

## Exact remaining blockers

### BLOCKER 1 — Production not deployed
- **Why:** No live HTTPS tenant endpoint proven from this environment  
- **Work:** Deploy RC to VPS; env secrets; migrations; workers; health checks  
- **Test:** `/health/ready` 200; login; one POS sale  
- **Automation:** Can prepare compose/K8s; **cannot** operate your VPS alone without credentials  
- **Owner:** Required

### BLOCKER 2 — Offline POS endurance / marketing claims
- **Why:** Code foundation + recovery export + heartbeat are PARTIAL; physical 7-day endurance, multi-device reconnect certification, and alert dashboard are NOT RUN / absent  
- **Work:** Device certification + alert UX + OS lockdown OR remove offline claims from sales materials  
- **Test:** Physical offline 50+ sales + reconnect idempotency + 7-day window + recovery restore drill  
- **Automation:** Foundation + recovery JSON + heartbeat API shipped; remaining is certification + ops UX  
- **Owner:** Product decision + physical tests

### BLOCKER 3 — Physical device / platform certification
- **Why:** No Windows/Android/iPad/macOS verification evidence  
- **Work:** Run §51–§53 device tests  
- **Automation:** Cannot  
- **Owner:** Required

### BLOCKER 4 — Staging restore + load + pen test
- **Why:** Operational proof missing  
- **Work:** Execute DR restore drill, load suite, schedule external pen test  
- **Automation:** Scripts/docs only  
- **Owner / external:** Required

### BLOCKER 5 — Multi-company (only if sold as multi-company SaaS)
- **Why:** Tenant has one company profile today  
- **Work:** New Company entity under Tenant + switcher + isolation — large redesign  
- **Automation:** Possible as dedicated epic  
- **Owner:** Scope decision — **NOT required** if you sell one-company-per-tenant MVP

---

## ACTION REQUIRED FROM OWNER

1. Deploy release candidate to staging/production VPS.  
2. Configure production domain / HTTPS / secrets / SMTP.  
3. Run DB migrations including `20260917_0105`, `20260917_0106`, and `20260917_0107`.  
4. Decide: **defer offline marketing** OR fund endurance/device-alert epic before launch (foundation + recovery + heartbeat already in code).  
5. Connect physical Windows POS; run online sale + (if claiming offline) offline protocol + recovery export drill.  
6. Connect Android tablet; repeat.  
7. Perform staging restore drill; record RPO/RTO.  
8. Execute load test against staging.  
9. Arrange external penetration test.  
10. Review this report and `docs/GO_LIVE_CHECKLIST.md`; sign go-live only when blockers cleared.

---

## Recommended commercial MVP positioning (honest)

**Ship now as:** Multi-tenant online ERP — inventory, purchasing, sales, POS, accounting, tax, credit, multi-store entitlements, store membership RBAC, platform-assigned subscriptions.

**Do not claim yet:** Certified 7-day offline POS endurance, multi-company under one login, paid self-serve checkout, platform pen-test complete, hardware universal compatibility, device alert/MDM lockdown.
