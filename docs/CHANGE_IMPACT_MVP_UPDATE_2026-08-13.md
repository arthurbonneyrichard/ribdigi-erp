# Change-Impact Audit — Updated Commercial MVP Prompt (2026-08-13)

**Status:** Accepted baseline for Stage 162+  
**Product:** RIBDIGI BUSINESS ERP — Commercial MVP v1.0  
**Tip at audit:** Stage 161 freeze ADR-329 (`989739c`)  
**Rule:** Do not restart the project. Preserve working engines. Extend / refactor only where required.

## Executive summary

Most core tenant ERP engines (inventory, stock, sales, POS online, purchasing, accounting, reports, backup, platform console) are **COMPLETE** for MVP honesty. The updated prompt’s largest **new** gap is **Offline-first / PWA / Sync** (greenfield). The largest **refactor** is **tenant navigation IA** (Stage 95 Commerce/Operations flat sections → approved expandable parents). Deferred ADRs (002/003/005) and honesty flags remain **false** — do not claim Complete.

---

## What is preserved (do not rebuild)

| Area | Status | Notes |
|------|--------|-------|
| Platform vs Tenant separation | COMPLETE | `/platform/*` + `PlatformShell`; tenant `Shell` |
| Auth / RBAC module+action | COMPLETE | Soft-delete users (ADR-003) |
| Role-aware dashboards | COMPLETE | Cashier / store_manager / executive filters |
| Inventory / Stock engines | COMPLETE | Tabs + APIs; transfers/counts/movements |
| Sales / Purchasing / Credit | COMPLETE | Real AR/AP + journals |
| Online POS | COMPLETE | Sessions, tenders, receipts, barcode/QR |
| Accounting reports + path CSVs | COMPLETE | Stages 159–161 path exports |
| Backup `.ribbak` | COMPLETE | No fake success |
| Docker / Redis / RabbitMQ / Celery | COMPLETE | Main `ci.yml` deploy-free |
| Stages 1–161 freezes | IN FORCE | Bugfix/doc only unless superseding ADR |

---

## Impact matrix (updated prompt → current state)

| Updated requirement | Current | Verdict | Files / surface | DB | API | Frontend | Security | Recommended action |
|---------------------|---------|---------|-----------------|----|-----|----------|----------|--------------------|
| Platform Owner dashboard KPIs | Real tenant/lifecycle KPIs; MRR null | COMPLETE (honest) | `platform/dashboard`, `platform_api.py` | — | — | — | Tenant isolation OK | Keep; never fabricate MRR |
| Platform tenant mgmt | List/activate/suspend | COMPLETE | `platform/tenants` | — | — | — | OK | Keep |
| Tenant RBAC + custom roles | Module/action model | COMPLETE | `rbac.py`, `/roles` | — | — | admin pages | OK | Keep; do not rename to `products.view` without migration plan |
| User suspend/archive | `is_active` only | PARTIAL | `users`, ADR-003 | Maybe later | Extend | Users UI | Soft-delete only | Defer archive/hard-delete (ADR-003) |
| User↔store/warehouse assign | Branch/dept + manager_id | MISSING | ADR-005 | Yes if opened | Yes | Users/Stores | Critical tenancy | Defer per ADR-005 or open dedicated stage |
| Tenant nav parents (§37) | Stage 95 Commerce/Ops flat | REQUIRES REFACTOR | `Shell.tsx` | No | No | Shell only | Menu gating unchanged | **Stage 162 N1** |
| Role-aware dashboards | Implemented | COMPLETE | `dashboard_views.py` | — | — | dashboard | Backend enforced | Keep |
| Inventory / Stock / Sales / Purchase | Engines + UI | COMPLETE | module pages | — | — | — | OK | Keep; nav regroup only |
| POS Hold/Resume | Stage 165 H1 Partial / Stage 166 S1 soft reserve | PARTIAL | `pos_held_carts` + `reserved_qty` | Yes | — | POS | Soft reserve optional; not Offline Complete | Offline Complete later |
| Billers CRUD | Alias to salesperson report | PARTIAL | Shell link | Yes if CRUD | Yes | People | — | Defer (honesty) |
| Parallel Income module | P&L alias | PARTIAL | Accounting | — | — | — | — | Defer |
| Finance reports path CSVs | Stages 160–161 | COMPLETE | `finance_ops_export.py` | — | — | Reports/Accounting | RBAC | Keep |
| Offline / PWA / Sync | Stage 163–165 | PARTIAL | PWA+queue+IDB+Hold | Yes | Yes | PWA+POS | Device/tenant checks | Client queue+Partial Hold; Offline Complete **166+** |
| Device registration | Stage 163 V1 | COMPLETE (MVP) | `offline_devices` | Yes | — | Settings | Soft revoke | Keep |
| Sync APIs `/sync/*` | Stage 164 Q1–C1 | COMPLETE (MVP) | `sync_engine.py` | Yes | — | — | Idempotency | Keep; conflict resolve UX later |
| Connectivity status UI | Stage 163 C1 | COMPLETE (MVP) | Shell | No | No | Chrome | — | Keep |
| Idempotency offline txs | Stage 164 I1 | COMPLETE (MVP) | `client_request_id` | Yes | — | POS/sync | Unique per tenant | Keep |
| Idempotency offline txs | None | MISSING | POS schemas | Unique constraints | Yes | Queue | Critical | With sync push |
| Backup / VPS | Complete packaging | COMPLETE | backup, helm/compose | — | — | — | Secrets | Keep |
| Paid billing | Deferred ADR-002 | MISSING (honest) | platform billing | — | — | — | — | Keep deferred; flags false |

---

## New requirements that affect completed work

1. **Navigation IA (§37)** — supersedes Stage 95 section labels; must not duplicate pages; preserve deep-links and RBAC menu gating. Stage 95 shell tests need amendment under Stage 162.
2. **Offline/PWA (§13–30)** — does **not** replace online POS; extends it. Do not weaken online transactional integrity.
3. **Permission naming (`products.view`)** — current model is `inventory`+`read`; mapping/aliases only if required — do not break existing grants.
4. **User store assignment (§7)** — conflicts with ADR-005 deferral; open only via explicit ADR amendment.
5. **Hold/Resume** — previously deferred; may land with offline cart queue.

---

## Safest incremental plan (mapped to UPDATE stages)

| Priority | Update stage | Incremental Stage | Focus |
|----------|--------------|-------------------|-------|
| P0 now | UI §37 + Update 1 polish | **162** | Approved expandable navigation hierarchy |
| P0 next | Update 8 start | **163** | Offline honesty ADR + PWA shell + connectivity chrome + device model skeleton |
| P0 | Update 8 | **164+** | Sync queue client + `/sync/*` + idempotent POS push |
| P1 | Update 7 residual | later | POS Hold/Resume (online + offline) |
| P1 | Update 4 residual | later | Billers CRUD (if product still requires) |
| Deferred | ADR-002/003/005 | post-MVP or dedicated ADR open | Billing / hard-delete / membership |

---

## Honesty flags (must remain false)

`mrr_fabricated_claimed`, `billing_complete_claimed`, `subscriptions_live_claimed`, `user_store_membership_claimed`, `hard_delete_claimed`, `sections_1_3_verified`, `section_7_signed`, `go_live_claimed`, `attestation_claimed`.

Do **not** claim Offline Complete until sync + idempotency + conflict tests pass end-to-end.

---

## Stage 162 decision (opened from this audit)

**Tenant MVP Approved Navigation Hierarchy Fidelity** — expand/collapse parents matching §37; no new duplicate modules; all existing hrefs preserved; Offline remains MISSING until Stage 163+.

## Stage 163 decision (opened after Stage 162 freeze)

**Tenant MVP Offline Foundation Fidelity** — PWA shell + connectivity chrome + device registration + `/sync/status` honesty. Sync push/pull/conflicts and offline sales remain Stage 164+. Do not claim Offline Complete.

## Stage 164 decision (opened after Stage 163 freeze)

**Tenant MVP Sync Queue + Idempotent Offline POS Fidelity** — real queue tables, push/pull/ack/conflicts, `client_request_id` idempotency. Hold/Resume and Offline Complete remain Stage 165+.

## Stage 165 decision (opened after Stage 164 freeze)

**Tenant MVP Offline Client Queue + Hold/Resume + Conflict Resolve Fidelity** — IndexedDB queue, Partial Hold/Resume (no stock reserve), conflict resolve without silent re-apply. Offline Complete remains Stage 166+.

## Stage 166 decision (opened after Stage 165 freeze)

**Offline Complete Hardening Fidelity** — stock-safe offline catalog cache (C1), accept_client safe re-apply (A1), Hold soft `product.reserved_qty` reserve (S1). Offline Complete remains deferred (Stage 167+).

## Stage 167 decision (opened after Stage 166 freeze)

**Offline Complete E2E Hardening Fidelity** — catalog TTL/refresh (T1), conflict re-apply UX polish (U1), Hold soft-reserve expiry/cleanup (E1). Offline Complete remains deferred (Stage 168+).

## Stage 168 decision (opened after Stage 167 freeze)

**Offline Complete Attestation Fidelity** — SW static-cache contract (W1), offline sale/flush API attestation (F1), device revoke mid-queue honesty (R1). Offline Complete product claim remains deferred (Stage 169+).
