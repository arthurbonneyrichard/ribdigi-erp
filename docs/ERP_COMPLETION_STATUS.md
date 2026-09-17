# ERP Completion Status — Market readiness

**Last updated:** 2026-09-17 (commercial readiness: Main Store seed + User↔Store RBAC)  
**Overall estimate (SMB retail / wholesale online core):** ~**94%**  
**Go-Live:** **NOT READY** until production deploy + (if marketed) offline epic — see `docs/COMMERCIAL_READINESS_REPORT.md`

## This session (commercial)

- Default **Main Store** on tenant seed (entitlement-safe via `create_store`)
- **UserStoreMembership** model/migration + `GET/PUT /users/{id}/stores`
- POS store list + open session enforce membership (`store_access.py`)
- Users UI store assignment column
- Docs: tenancy SUPERSEDED markers; `GO_LIVE_CHECKLIST.md`; `COMMERCIAL_READINESS_REPORT.md`
- Platform billing copy: entitlements assign-only (no fake checkout)

## Prior store parity

Dashboard/Accounting/Reports/Inventory/Purchasing/Expenses header store wiring; auth gate.

## Intentionally out of scope / FAIL until built

- 7-day offline POS, device heartbeat/lockdown
- Multi-company under one Tenant (MVP = Tenant is the company profile)
- Paid payment gateway
- Physical platform certification
