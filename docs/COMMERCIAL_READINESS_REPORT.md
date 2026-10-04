# RIBDIGI ERP COMMERCIAL READINESS REPORT

**Date:** 2026-09-17  
**Code HEAD (this workstream):** see branch `production`  
**Principle:** No false completion. Automation cannot execute physical POS / VPS / pen tests.

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
