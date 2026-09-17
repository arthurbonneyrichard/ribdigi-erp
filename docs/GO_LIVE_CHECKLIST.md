# RIBDIGI ERP — GO-LIVE CHECKLIST (authoritative)

**Date:** 2026-09-17  
**Branch evidence:** commercial readiness work on `cursor/ai-expense-store-filters-7aae`  
**Rule:** Evidence required. Docs ≠ implementation. Local Docker ≠ production.

Legend: **PASS** | **FAIL** | **BLOCKED** | **NOT REQUIRED FOR MVP**

| Category | Item | Status | Evidence / notes |
|----------|------|--------|------------------|
| Architecture | Shared schema + `tenant_id` | PASS | `docs/ADR_001_TENANCY.md`; models |
| Architecture | Tenant == Company (1:1 MVP) | PASS | `store_entitlements.py`; multi-company under one tenant = POST-MVP |
| Database | Migrations apply | PASS | Alembic tree incl. `20260917_0105_user_store_memberships`, `20260917_0106_transaction_client_request_id` |
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
| Offline | IndexedDB / 7-day / SW | PARTIAL | `frontend/lib/posOffline.ts`, `/sw.js`, `client_request_id` idempotency; endurance NOT RUN |
| POS Devices | Heartbeat / lockdown | FAIL | Not implemented — POST-MVP unless marketed |
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
2. **Offline POS marketing** — foundation **PARTIAL** in code; do not claim certified 7-day endurance until physical tests + recovery export + heartbeat  
3. **Physical POS verification** (OWNER) — Windows/Android devices  
4. **Staging restore + load drill** (OWNER)  
5. **External pen test** (EXTERNAL)

## Post-MVP (do not block launch if not marketed)

- Multi-company under one Tenant  
- User↔POS terminal binding (`ASSIGNED_POS_ONLY`)  
- Offline endurance certification, recovery export package, device heartbeat dashboard, OS lockdown guides  
- PITR live drill, paid payment provider  
- HR / MRP / Open Banking  
