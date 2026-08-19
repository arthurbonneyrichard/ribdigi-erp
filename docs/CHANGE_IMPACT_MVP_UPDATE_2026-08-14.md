# CHANGE IMPACT — Commercial MVP Product Update (2026-08-14)

**Product:** RIBDIGI BUSINESS ERP — Commercial MVP v1.0  
**Company / Platform Owner:** Ribdigi House  
**Motto:** One System. Total Business Control.  
**Status:** Accepted audit (Stage 367 packaging)  
**Related:** [CURSOR_HANDOFF.md](../CURSOR_HANDOFF.md) · [PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md) · [CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md](CHANGE_IMPACT_MVP_UPDATE_2026-08-13.md) · ADR-002 · ADR-005 · ADR-137 · Stage 366 freeze ADR-740

## Critical instruction honored

This is an **update to the existing `ribdigi-erp` repository**. Do **not** restart, rebuild from scratch, duplicate engines, discard working features, reset the database, or invent fake Completes. Inspect → classify → preserve → extend → migrate safely → test.

Where this update conflicts with older outlines (including Stage 366 runner-up Business Metrics Pack packaging), **this product-update continuity track takes precedence** for Stage 367+.

---

## Executive verdict

| Area | Verdict |
|------|---------|
| Dual-console Platform Owner vs Tenant (ADR-137) | **COMPLETE** (MVP honesty) |
| Platform dashboard real KPIs (no fake MRR) | **COMPLETE** (billing deferred ADR-002) |
| Platform tenant list / activate / suspend | **COMPLETE** |
| Tenant RBAC + soft-delete users (ADR-003/004) | **COMPLETE** (module+action model) |
| Tenant expandable nav hierarchy (Stage 162) | **COMPLETE** |
| Inventory / Stock / Sales / Purchase / POS / People / Stores / Warehouse | **COMPLETE** (MVP engines; extend not rebuild) |
| Finance double-entry + reports + logical backup | **COMPLETE** (MVP) |
| Role-aware dashboards (cashier / store manager / executive) | **COMPLETE** |
| Offline / PWA / sync foundation | **PARTIAL** — Offline Complete still **MISSING** |
| User↔store membership (ADR-005) | **MISSING** (deferred by ADR) |
| Paid billing / subscription revenue Completes (ADR-002) | **MISSING** (deferred; `mrr: null`) |
| `products.*` / `stock.*` permission key rename | **REQUIRES REFACTOR** only if product mandates rename — **do not** rename without migration plan |
| Fake demo tenants / fake success APIs | **Not introduced** — keep blocked |

**Do not claim Offline Complete, paid billing Complete, ADR-005 membership Complete, go-live Completes, or attestation Completes.**

---

## STEP 2 — Requirement classification table

| Updated requirement | Current implementation | Status | Files / surfaces (representative) | DB | API | FE | Security | Recommended action |
|---------------------|------------------------|--------|-----------------------------------|----|-----|----|----------|--------------------|
| Platform Owner vs Tenant separation | ADR-137 principal; reserved `ribdigi-platform`; middleware + `require_platform_permission` | COMPLETE | `backend/app/platform_const.py`, `security.py`, `frontend/middleware.ts`, `PlatformShell.tsx` | none | none | none | keep | Preserve |
| `/platform/dashboard` real KPIs | Live SQL aggregates; billing block `deferred` / `mrr: null` | COMPLETE | `frontend/app/platform/dashboard/page.tsx`, `backend/app/platform.py`, `platform_api.py` | none | none | polish only | keep | Preserve; never fabricate MRR |
| Platform tenant management | List/filter, provision, suspend, activate, lifecycle | COMPLETE | `frontend/app/platform/tenants/`, `platform_api.py` | none | none | none | keep | Preserve |
| Tenant user CRUD + roles | Soft-delete users; system + custom roles; branch/dept | PARTIAL | `frontend/app/users/`, `backend/app/roles.py`, `api.py` users | ADR-005 later | membership later | store assign UI later | keep tenant scope | Extend for ADR-005 when opened — do not fake membership |
| Granular `products.*` / `stock.*` keys | Module+action (`inventory`×`read`/`write`); aliases Stage 84 | PARTIAL vs prompt naming | `backend/app/rbac.py`, ADR-004 | rename would need migration | alias layer optional | menu unchanged | do not weaken | Prefer aliases over rename; document if prompt insists |
| Tenant dashboard KPIs + charts | Tenant-scoped dashboard + charts | COMPLETE | `frontend/app/dashboard/page.tsx`, `dashboard_views.py`, `dashboard_scope.py` | none | none | none | keep | Preserve |
| Role-aware dashboards | cashier / store_manager / executive views | COMPLETE | `dashboard_views.py`, `dashboard_scope.py` | none | none | none | keep | Preserve; ADR-005 expands multi-store later |
| Expandable nav (Inventory…Settings) | Stage 162 Shell parents + User Management | COMPLETE | `frontend/components/Shell.tsx` | none | none | leaf pages as needed | menu≠security | Preserve hierarchy; add leaf routes only when APIs exist |
| Inventory / barcode / QR / expiry / low stock | Product engines + packaging | COMPLETE | inventory FE/BE | none for audit | none | none | keep | Preserve |
| Stock adjust / transfer / count / reconcile | Stock movement model | COMPLETE | stock modules | none | none | none | keep | Preserve |
| Sales / invoice / quotation / returns | Sales engines | COMPLETE | sales modules | none | none | none | keep | Preserve |
| POS (online) transactional | POS sale + stock + payments | COMPLETE | `frontend/app/pos/page.tsx`, `pos_record.py` | none | none | none | keep | Preserve |
| Purchase / PO / GRN / returns | Purchasing engines | COMPLETE | purchasing modules | none | none | none | keep | Preserve |
| Finance & Accounts double-entry | COA, journals, TB, P&L, liquid, recon | COMPLETE | `frontend/app/accounting/page.tsx` | none | none | none | keep | Preserve; AR/AP shells redirect to credit |
| AR/AP accounting surface “live Complete” | Stage 232 packaging + Stage 366 RG index | PARTIAL packaging; live Complete MISSING | Stage 366 docs / credit routes | none | no new AR engine | shells exist | honesty flags false | Do not claim new AR/AP engine |
| People (customers / suppliers / billers) | CRM-style modules | COMPLETE | people modules | none | none | none | keep | Preserve |
| Stores / Warehouse | Multi-store / warehouse | COMPLETE | stores/warehouse modules | ADR-005 later | later | later | keep | Preserve |
| Reports + PDF/Excel/CSV | Reports suite | COMPLETE | `frontend/app/reports/page.tsx` | none | none | none | keep | Preserve |
| Settings / security / templates | Company + settings surfaces | COMPLETE / PARTIAL leaf depth | company/settings pages | as needed | as needed | leaf polish | keep | Extend leaf settings only |
| Offline-first POS + queue + idempotency + conflicts | IndexedDB queue, catalog, push/pull, conflicts, `client_request_id` | PARTIAL | `offlineQueue.ts`, `offlineCatalog.ts`, `sync_engine.py`, POS page | possible later | sync already | queue UI | device auth | Extend toward Offline Complete; never claim Complete until attestation workflow passes |
| PWA manifest + SW | Manifest + static SW; API not cached | PARTIAL | `public/manifest.webmanifest`, `sw.js`, `ServiceWorkerRegister.tsx` | none | none | install UX polish | no secret cache | Extend shell; keep API uncached |
| Device registration & Offline & Sync settings | Devices under Company `#offline-sync` | PARTIAL | `company/page.tsx`, `/offline/devices` APIs | none | none | optional dedicated Settings children | revoke enforced | Extend Settings IA without duplicate nav |
| Sync APIs `/api/v1/sync/*` | status/push/pull/ack/conflicts | COMPLETE (MVP) | `api.py`, `sync_engine.py` | none | broaden op types carefully | none | tenant+device+idempotency | Preserve; extend ops only with tests |
| Connectivity ONLINE/OFFLINE/SYNC* | ONLINE/OFFLINE badge only | PARTIAL | `Shell.tsx` connectivity-badge | none | optional status hook | SYNCING/SYNC ERROR | none | **Next incremental:** wire queue depths to badge |
| Backup / restore real `.ribbak` | Logical encrypted backup | COMPLETE | `backup.py`, backup UI | none | none | none | keep | Preserve; live PITR/DR still MISSING |
| VPS / Docker deploy prep | Docker compose / guides | PARTIAL → COMPLETE packaging | deploy docs, docker | none | none | none | no public DB/Redis/RMQ | Preserve; main `ci.yml` deploy-free (Stage 18 C1) |
| No-fake-functionality / no demo tenants | Commercial product rules + ADR-002 honesty | COMPLETE posture | fixtures test-only | — | — | — | keep | Never weaken |
| Paid billing Completes | Deferred | MISSING | ADR-002 | future | future | future | future | Do not fabricate |
| Go-live / §7 / attestation Completes | Deferred | MISSING | attestation packs | — | — | — | — | Do not claim |
| Offline Complete product claim | Attestation contracts only | MISSING | `OFFLINE_COMPLETE_*` | — | — | — | — | Continue hardening; claim only after Stage 41-style acceptance workflow |

---

## STEP 3 — Preserve (do not rebuild)

Keep working engines and consoles:

- Platform principal + `/platform/*` console (ADR-137)
- Tenant ERP shell + Stage 162 navigation hierarchy
- PostgreSQL + Alembic migration chain (no reset)
- RBAC module+action enforcement on APIs
- POS online transactional path + soft Hold reserves
- Sync MVP (`/sync/*`) + offline device registry
- Inventory / stock movements / purchasing / sales / accounting ledger / reports / logical backup
- Role-aware dashboard views
- Soft-delete users (ADR-003)
- Billing honesty (`mrr: null`, ADR-002)
- Packaging Completes ≠ product Completes (remaining-gate indexes through Stage 366)

---

## STEP 4 — Requirements that affect already-completed work

| Prompt ask | Interaction with completed work | Safe handling |
|------------|---------------------------------|---------------|
| `products.*` / `stock.*` permission strings | Would collide with ADR-004 module catalog Completes | Add **aliases** only; do not rename modules without migration + dual-read |
| Dedicated Settings → Offline & Sync children | Company `#offline-sync` already works | Refactor **navigation labels/anchors**; do not fork a second settings stack |
| Offline Complete / PWA “full app” | Would over-claim Stage 163–179+ honesty | Keep PARTIAL; extend queue/badge/tests; claim only after acceptance workflow |
| User↔store assignment | ADR-005 deferred Completes | New schema+API when Stage opens; do not fake Completes via UI-only |
| Platform subscription revenue KPIs | ADR-002 deferred | Keep null/deferred blocks |
| AR/AP “engine” Completes | Stage 232/366 packaging only | Credit redirect remains; no parallel ledger |
| Business Metrics Pack runner-up (ADR-740) | Packaging-only next stage | **Superseded for Stage 367** by this product-update continuity track; may reopen later as Stage 368+ if still distinct |

---

## STEP 5 — Safest incremental implementation plan

### Principles

1. One workstream at a time; full AC + automated tests before the next.
2. Prefer extending proven engines (FX→connectors pattern; sync→more op types).
3. Alembic only when schema required; never wipe migrations.
4. Frontend hiding ≠ security; APIs enforce tenant + RBAC + device.
5. Honesty flags stay false until real Completes ship.

### Ordered workstreams (post–Stage 367 audit packaging)

| Priority | Workstream | Why safe | Exit signal |
|----------|------------|----------|-------------|
| **P0** | Connectivity badge: ONLINE / OFFLINE / SYNCHRONIZING / SYNC ERROR using real queue depths | FE-only + existing offlineQueue; no schema | Badge tests + Shell cite; Offline Complete still false |
| **P0** | Settings IA: Offline & Sync children pointing at existing `#offline-sync` / devices | Nav-only; no duplicate APIs | Manual + launch cites |
| **P1** | Sync push op coverage + replay/idempotency test hardening | Extends `sync_engine` | pytest green; no duplicate sales |
| **P1** | Conflict UX polish for managers (existing conflict APIs) | UI on existing endpoints | No silent stock overwrite |
| **P2** | Permission alias map for prompt-style keys (`products.view`→`inventory`+`read`) | Dual-accept; no rename | alias tests |
| **P2** | ADR-005 store membership (when opened) | New tables + tenant-scoped APIs | ADR-005 Completes only after E2E |
| **Deferred** | Paid billing / MRR | ADR-002 | Keep deferred |
| **Deferred** | Offline Complete product claim | Attestation workflow | Only after §41 acceptance path |
| **Deferred** | Schema-per-tenant / go-live Completes | ADR-001 / launch gates | Do not reopen residual/golive Completes |

### Explicit non-goals for this update track

- Restarting the repo or parallel ERP stack
- Demo tenants / fake dashboard numbers / fake backup success
- Claiming Offline Complete or paid billing Complete
- Hard-deleting users with transaction attribution
- Main `ci.yml` production deploy (Stage 18 C1 remains)

---

## STEP 6 — Continue from current state

1. Stage 367 packages this audit (index + blockers + pointers + fidelity) under ADR-741 / ADR-742.
2. **P0 shipped with Stage 367 follow-through (same continuity track):** Shell connectivity chrome now surfaces ONLINE / OFFLINE / SYNCHRONIZING / SYNC ERROR from IndexedDB queue depths (`frontend/components/Shell.tsx`, `frontend/lib/offlineQueue.ts`). Settings nav adds Offline & Sync children pointing at `/company#offline-sync`. **Offline Complete remains MISSING.**
3. Next after Stage 367 freeze packaging: Sync push/idempotency hardening (P1), conflict UX polish; optional Connectivity Sync Status Pack remaining-gate packaging (`CONNECTIVITY_SYNC_STATUS_PACK_*`) if a distinct packaging stage is opened. Business Metrics Pack may return later if still distinct.

---

## Decision log

**Stage 367 decision (opened after Stage 366 freeze):** Tenant MVP Commercial Continuity Change-Impact Index Fidelity — package this 2026-08-14 product-update audit as the authoritative continuity index (I1), blocker matrix for Offline Complete / ADR-002 / ADR-005 / go-live / attestation (B1), and pointers into Stage 366 / Stage 329 / ADR-002 / ADR-005 (P1). Prefixed `MVP_PRODUCT_UPDATE_PACK_*` remaining-gate (`_REMAINING_GATE` / `_RG_*`). Distinct from Stage 366 AR/AP accounting surface pack remaining-gate and deferred Business Metrics packaging. Do not reopen `RESIDUAL_RISK_PACK_*` or `GOLIVE_PACK_*`. Open ADR-741 / freeze ADR-742.
