# RIBDIGI ERP — GO-LIVE CHECKLIST (authoritative)

**2026-10-03 audit status: NOT READY.** Do not treat the 2026-09-17 rows as reconfirmed. This audit did not click through every industry workflow, did not restore a production backup, and did not run the full backend suite.

**Date:** 2026-09-17 (historical snapshot below)  
**Branch evidence:** commercial readiness work on the production release branch  
**Rule:** Evidence required. Docs ≠ implementation. Local Docker ≠ production.

## Audit 2026-10-03 (local, not deployed)

Supported industries in product code: Retail, Pharmacy, Wholesale, Retail + Wholesale. Hotel, FMCG, and Hospital remain implemented verticals; they were not removed and their data was not deleted. Offline Complete, paid checkout, and a hospital information system are not claimed.

| Area | Status | Evidence |
|------|--------|----------|
| Tenant isolation matrix (SQLite) | PASS | `tests/test_tenant_isolation_matrix.py` in the 48-test slice |
| Trade channels, platform owner, loyalty/gift/hospital, ops repairs, logical backup drill | PASS | Same slice: 48 passed |
| Sales-by-store limited to assigned stores | PASS | `tests/test_sales_by_store.py` + `tests/test_reports.py`: 9 passed |
| POS sale when the store warehouse quantity is zero | PASS | `tests/test_out_of_stock.py::test_pos_search_store_warehouse_zero_and_sale_409` |
| Store scope on every report (returns, inventory, purchasing, finance) | FAIL | Those routes still omit `report_store_kwargs` |
| Dashboard product stock counts for an assigned store | FAIL | `dashboard.py` product totals stay tenant-wide |
| Signed-in Retail / Pharmacy / Wholesale / combo walkthrough | BLOCKED | No authenticated browser session in this audit |
| Operator backup restore of a real database | BLOCKED | Logical drill tests only; production data was not restored |
| Frontend production build | BLOCKED | Not run in this audit |
| Full backend suite and Alembic against a staging database | BLOCKED | Not run in this audit |

Legend: **PASS** | **FAIL** | **BLOCKED** | **NOT REQUIRED FOR MVP**

| Category | Item | Status | Evidence / notes |
|----------|------|--------|------------------|
| Architecture | Shared schema + `tenant_id` | PASS | `docs/ADR_001_TENANCY.md`; models |
| Architecture | Tenant == Company (1:1 MVP) | PASS | `store_entitlements.py`; multi-company under one tenant = POST-MVP |
| Database | Migrations apply | PASS | Alembic tree incl. `20260917_0105`–`0107` (membership, client_request_id, pos_devices) |
| Tenant Isolation | JWT + query filters | PASS | `security.py`, isolation tests |
| Company Isolation | Multi-company child orgs | NOT REQUIRED FOR MVP | Company profile = Tenant; no second Company entity |
| Store Isolation | Entitlement + membership | PASS | `store_entitlements.py`; `store_access.py`; POS filter |
| RBAC | Module permissions | PASS | `rbac.py`, role nav |
| Inventory | Core stock flows | PASS | Existing inventory APIs/UI |
| Purchasing | PO / GRN / invoices | PASS | Existing purchasing module |
| Sales | Invoices / orders | PASS | Existing sales module |
| POS | Online shift + sale | PASS | `pos.py`, `/pos` UI |
| Accounting | CoA / journals / P&L | PASS | Accounting module |
| Tax | Tax rates / reports | PASS | Tax module |
| Credit | Customer credit | PASS | Credit module |
| Offline | IndexedDB / 7-day / SW | PARTIAL | `posOffline.ts`, `/sw.js`, `client_request_id`; recovery JSON; endurance NOT RUN |
| POS Devices | Heartbeat / lockdown | PARTIAL | Heartbeat API + `docs/POS_DEVICE_LOCKDOWN_GUIDE.md`; physical kiosk NOT VERIFIED |
| Backup | Logical backup API | PASS | `/backup`, DR runbook |
| Restore | Logical restore tested in CI | PASS | `test_logical_dr_drill_b1.py` |
| Security | Internal isolation/RBAC tests | PASS | Backend test suite |
| Performance | Live load certification | BLOCKED | Scripts exist; live VPS run = OWNER |
| Monitoring | Prod scrape/alerts | BLOCKED | OWNER / ops |
| Deployment | Prod HTTPS + secrets | BLOCKED | OWNER |
| Documentation | Tenancy drift marked | PASS | `ORIGINAL_README.md` SUPERSEDED notes |
| Support | Paid billing gateway | NOT REQUIRED FOR MVP | Platform assigns packages; truthful “Contact Ribdigi” |
| Rollback | Deploy rollback plan | BLOCKED | OWNER runbook |

## Launch blockers (must close or explicitly defer marketing)

1. **Production deployment** (OWNER) — domain, TLS, secrets, Postgres, workers  
2. **Offline POS marketing** — foundation **PARTIAL** in code (queue + recovery JSON + heartbeat); do not claim certified 7-day endurance until physical tests + alert UX  
3. **Physical POS verification** (OWNER) — Windows/Android devices  
4. **Staging restore + load drill** (OWNER)  
5. **External pen test** (EXTERNAL)

## Post-MVP (do not block launch if not marketed)

- Multi-company under one Tenant  
- User↔POS terminal binding (`ASSIGNED_POS_ONLY`)  
- Offline endurance certification, device alert dashboard (beyond last-seen table)  
- Physical kiosk verification per `docs/POS_DEVICE_LOCKDOWN_GUIDE.md`  
- PITR live drill, paid payment provider  
- HR / MRP / Open Banking  
