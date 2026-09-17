# ERP Completion Status — Market readiness

**Last updated:** 2026-09-17 (offline POS foundation + commercial readiness)  
**Overall estimate (SMB retail / wholesale online core):** ~**95%**  
**Go-Live:** **NOT READY** until production deploy + (if marketed) offline endurance certification — see `docs/COMMERCIAL_READINESS_REPORT.md`

## This session (commercial)

- Default **Main Store** on tenant seed (entitlement-safe via `create_store`)
- **UserStoreMembership** model/migration + `GET/PUT /users/{id}/stores`
- POS store list + open session enforce membership (`store_access.py`)
- Users UI store assignment column
- Docs: tenancy SUPERSEDED markers; `GO_LIVE_CHECKLIST.md`; `COMMERCIAL_READINESS_REPORT.md`
- Platform billing copy: entitlements assign-only (no fake checkout)

## Prior store parity

Dashboard/Accounting/Reports/Inventory/Purchasing/Expenses header store wiring; auth gate.

## This session (offline foundation)

- `client_request_id` on POS sales (DB unique + idempotent replay) — migration `20260917_0106`
- IndexedDB catalog/queue/device_state + 7-day offline auth envelope (`frontend/lib/posOffline.ts`)
- POS UI: online/offline banner, cash-only offline checkout, cached stock honesty, auto-flush queue
- Basic service worker shell cache (`public/sw.js`)

## Intentionally out of scope / FAIL until built or certified

- Physical 7-day offline endurance + multi-device reconnect certification
- Offline recovery export/import package; device heartbeat dashboard; OS lockdown guides
- Multi-company under one Tenant (MVP = Tenant is the company profile)
- Paid payment gateway
- Physical platform certification (Windows / Android / iPadOS / macOS)

